from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea, PostLog
import requests
from requests.auth import HTTPBasicAuth
import os
from datetime import datetime

# Importando as funções dos seus serviços
from services.ai_service import generate_text
from utils.scrapers import extrair_texto_da_url
from utils.ai_logic import preparar_contexto_brainstorm

# --- VERIFICAÇÃO DO SERVIÇO DE IMAGEM ---
try:
    from services.image_service import processar_imagem_featured
    # Este print aparecerá no terminal assim que o Flask carregar o módulo
    print("✅ Sucesso: OpenAI detectada e serviço de imagem carregado corretamente!")
except ImportError as e:
    processar_imagem_featured = None
    print(f"⚠️ ALERTA: Serviço de imagem não foi carregado! Erro: {e}")
except Exception as e:
    processar_imagem_featured = None
    print(f"❌ Erro inesperado ao carregar image_service: {e}")

content_bp = Blueprint('content', __name__)

# --- 1. FILA DE IDEIAS ---
@content_bp.route('/ideas')
@login_required
def ideas():
    site_id = request.args.get('site_id')
    query = ContentIdea.query.join(Blog).filter(Blog.user_id == current_user.id, ContentIdea.is_posted == False)
    if site_id and site_id.isdigit():
        query = query.filter(ContentIdea.blog_id == int(site_id))
    ideas_list = query.order_by(ContentIdea.created_at.desc()).all()
    return render_template('ideas.html', ideas=ideas_list)

# --- 2. GERAR IDEIAS COM IA ---
@content_bp.route('/generate-ideas', methods=['POST'])
@login_required
def generate_ideas():
    site_id = request.form.get('site_id')
    blog = Blog.query.filter_by(id=site_id, user_id=current_user.id).first()

    if not blog:
        flash('Selecione um site válido.', 'warning')
        return redirect(url_for('content.ideas'))

    try:
        # Gera 10 títulos baseados no nome do site configurado no models.py
        prompt = f"Gere 10 títulos de artigos para um blog sobre {blog.site_name}. Retorne um por linha."
        resultado = generate_text(prompt)
        
        if resultado:
            novas_ideias = [t.strip() for t in resultado.split('\n') if t.strip()]
            for titulo in novas_ideias:
                nova_ideia = ContentIdea(title=titulo.lstrip('0123456789. '), blog_id=blog.id)
                db.session.add(nova_ideia)
            db.session.commit()
            flash(f'{len(novas_ideias)} ideias geradas para {blog.site_name}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao gerar ideias: {str(e)}', 'danger')
    return redirect(url_for('content.ideas'))

# --- 3. PUBLICAR IDEIA (GERAR CONTEÚDO + IMAGEM + WP) ---
@content_bp.route('/publish-idea/<int:idea_id>', methods=['POST'])
@login_required
def publish_idea(idea_id):
    idea = ContentIdea.query.get_or_404(idea_id)
    blog = idea.blog

    try:
        # A. Gera o texto do artigo
        print(f"🤖 Gerando texto para: {idea.title}...")
        texto_final = generate_text(f"Escreva um artigo detalhado e otimizado para SEO sobre: {idea.title}")
        
        # B. Gera e faz upload da imagem (se o serviço estiver disponível)
        id_imagem = None
        print(f"DEBUG: Iniciando fluxo de imagem para '{idea.title}'")
        print(f"DEBUG: Serviço carregado? {processar_imagem_featured is not None}")
        print(f"DEBUG: Usuário tem plano? {current_user.plan_details is not None}")

        if current_user.plan_details:
            print(f"DEBUG: Plano permite imagens (has_images)? {current_user.plan_details.has_images}")

        if processar_imagem_featured and current_user.plan_details and current_user.plan_details.has_images:
            print("DEBUG: Condições aceitas. Chamando processar_imagem_featured...")
            auth_wp = (blog.wp_user, blog.wp_app_password)
            id_imagem = processar_imagem_featured(idea.title, blog.wp_url, auth_wp)
            print(f"DEBUG: Resultado do serviço de imagem (ID): {id_imagem}")
        else:
            print("DEBUG: Fluxo de imagem ignorado (verifique as condições acima)")
        # --- FIM DO DEBUG ---
            
            if id_imagem:
                print(f"📸 Imagem vinculada com sucesso! ID: {id_imagem}")
            else:
                print("⚠️ A imagem não pôde ser gerada, continuando apenas com o texto.")

        # C. Monta o pacote para o WordPress
        wp_payload = {
            'title': idea.title,
            'content': texto_final,
            'status': blog.post_status or 'publish'
        }
        if id_imagem:
            wp_payload['featured_media'] = id_imagem

        # D. Envia para a API do WordPress
        response = requests.post(
            f"{blog.wp_url.rstrip('/')}/wp-json/wp/v2/posts",
            auth=HTTPBasicAuth(blog.wp_user, blog.wp_app_password),
            json=wp_payload
        )

        if response.status_code in [200, 201]:
            # Sucesso: Marcar ideia como postada e registrar log
            idea.is_posted = True
            res_data = response.json()
            
            novo_log = PostLog(
                blog_id=blog.id,
                title=idea.title,
                status="Publicado",
                wp_post_id=res_data.get('id'),
                post_url=res_data.get('link')
            )
            db.session.add(novo_log)
            db.session.commit()
            
            flash(f"Artigo '{idea.title}' publicado com sucesso!", "success")
        else:
            flash(f"Erro no WordPress ({response.status_code}): {response.text}", "danger")

    except Exception as e:
        db.session.rollback()
        print(f"💥 Erro na publicação: {str(e)}")
        flash(f"Erro ao publicar: {str(e)}", "danger")

    return redirect(url_for('content.ideas'))

# --- 4. RELATÓRIOS E OUTRAS FUNÇÕES ---
@content_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    if request.method == 'POST':
        flash("Funcionalidade de post manual recebida!", "info")
        return redirect(url_for('content.post_report'))
    return render_template('manual_post.html')

@content_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed_content = None
    if request.method == 'POST':
        wp_url = request.form.get('wp_url')
        try:
            raw_text = extrair_texto_da_url(wp_url)
            if raw_text:
                processed_content = generate_text(f"Reescreva este artigo: {raw_text[:2000]}")
            else:
                flash("Não foi possível extrair texto desta URL.", "warning")
        except Exception as e:
            flash(f"Erro ao processar URL: {str(e)}", "danger")
    return render_template('spy_writer.html', processed_content=processed_content)

@content_bp.route('/post-report')
@login_required
def post_report():
    site_id = request.args.get('site_id')
    query = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id)
    if site_id and site_id.isdigit():
        query = query.filter(PostLog.blog_id == int(site_id))
    logs = query.order_by(PostLog.posted_at.desc()).all()
    return render_template('post_report.html', logs=logs)

@content_bp.route('/delete-idea/<int:idea_id>', methods=['POST'])
@login_required
def delete_idea(idea_id):
    idea = ContentIdea.query.join(Blog).filter(
        ContentIdea.id == idea_id, 
        Blog.user_id == current_user.id
    ).first_or_404()
    
    db.session.delete(idea)
    db.session.commit()
    flash('Ideia removida.', 'info')
    return redirect(url_for('content.ideas'))