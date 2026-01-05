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

# Importação do serviço de imagem da pasta services
try:
    from services.image_service import processar_imagem_featured
except ImportError:
    processar_imagem_featured = None

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
        # CORREÇÃO: Usando 'site_name' conforme o seu models.py
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
        flash(f'Erro: {str(e)}', 'danger')
    return redirect(url_for('content.ideas'))

# --- 3. PUBLICAR IDEIA (IA + IMAGEM) ---
@content_bp.route('/publish-idea/<int:idea_id>', methods=['POST'])
@login_required
def publish_idea(idea_id):
    idea = ContentIdea.query.get_or_404(idea_id)
    blog = idea.blog

    try:
        # 1. Gera o conteúdo
        texto_final = generate_text(f"Escreva um artigo detalhado sobre: {idea.title}")
        
        # 2. Lógica de Imagem (ajustado para seus modelos)
        id_imagem = None
        # Verifica se o plano do usuário permite imagens
        if processar_imagem_featured and current_user.plan_details and current_user.plan_details.has_images:
            auth_wp = (blog.wp_user, blog.wp_app_password)
            id_imagem = processar_imagem_featured(idea.title, blog.wp_url, auth_wp)

        # 3. Payload para o WordPress
        wp_payload = {
            'title': idea.title,
            'content': texto_final,
            'status': blog.post_status or 'publish'
        }
        if id_imagem:
            wp_payload['featured_media'] = id_imagem

        # 4. Envio para o WordPress
        response = requests.post(
            f"{blog.wp_url.rstrip('/')}/wp-json/wp/v2/posts",
            auth=HTTPBasicAuth(blog.wp_user, blog.wp_app_password),
            json=wp_payload
        )

        if response.status_code in [200, 201]:
            # MARCA COMO POSTADO
            idea.is_posted = True
            
            # CRIA O LOG NO BANCO DE DADOS (Importante!)
            novo_log = PostLog(
                blog_id=blog.id,
                title=idea.title,
                status="Publicado",
                wp_post_id=response.json().get('id'),
                post_url=response.json().get('link')
            )
            db.session.add(novo_log)
            db.session.commit()
            
            flash(f"Artigo '{idea.title}' publicado com sucesso!", "success")
        else:
            flash(f"Erro no WordPress ({response.status_code}): {response.text}", "danger")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao publicar: {str(e)}", "danger")

    return redirect(url_for('content.ideas'))

# --- 4. POSTAGEM MANUAL (O que estava faltando) ---
@content_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    if request.method == 'POST':
        # Aqui você implementaria a lógica de receber o formulário do utilizador
        # e enviar para o WordPress sem usar a IA para o texto.
        flash("Funcionalidade de post manual recebida!", "info")
        return redirect(url_for('content.post_report'))
    return render_template('manual_post.html') # Você precisará criar este HTML

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