from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea, PostLog
import requests
from requests.auth import HTTPBasicAuth
import os
from datetime import datetime

# Importando serviços
from services.ai_service import generate_text
try:
    from services.image_service import processar_imagem_featured
except ImportError:
    processar_imagem_featured = None

# Importando utilitários
from utils.scrapers import extrair_texto_da_url
from utils.ai_logic import preparar_contexto_brainstorm

content_bp = Blueprint('content', __name__)

# PADRONIZAÇÃO DO EMAIL DEMO (Conforme definido no reset_db.py)
DEMO_EMAIL = 'demo@wpautoblog.com.br'

def enviar_para_wordpress(conteudo, titulo, id_imagem, blog):
    """Função centralizada para enviar conteúdo ao WordPress via REST API."""
    # TRAVA DE SEGURANÇA: Simula sucesso para conta demo sem gastar recursos
    if current_user.email == DEMO_EMAIL:
        return type('Response', (object,), {'status_code': 201, 'json': lambda: {'link': 'https://wp.autoblog.com.br/post-demo', 'id': 999}})
    
    wp_payload = {
        'title': titulo,
        'content': conteudo,
        'status': blog.post_status or 'publish'
    }
    if id_imagem:
        wp_payload['featured_media'] = id_imagem

    try:
        response = requests.post(
            f"{blog.wp_url.rstrip('/')}/wp-json/wp/v2/posts",
            auth=HTTPBasicAuth(blog.wp_user, blog.wp_app_password),
            json=wp_payload,
            timeout=30
        )
        return response
    except Exception as e:
        print(f"Erro na conexão com WordPress: {e}")
        return None
    
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
        # A trava de geração de texto já existe dentro do ai_service.generate_text
        prompt = f"Gere 10 títulos de artigos para um blog sobre {blog.site_name}. Retorne um por linha, sem markdown."
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
    # TRAVA DE SEGURANÇA PARA CONTA DEMO
    if current_user.email == DEMO_EMAIL:
        flash("Simulação de publicação concluída com sucesso (Modo Demo).", "success")
        return redirect(url_for('content.ideas'))

    if current_user.credits <= 0:
        flash("Saldo de créditos insuficiente.", "warning")
        return redirect(url_for('content.ideas'))
    
    idea = ContentIdea.query.get_or_404(idea_id)
    blog = idea.blog

    try:
        texto_final = generate_text(f"Escreva um artigo detalhado sobre: {idea.title}")
        
        id_imagem = None
        if processar_imagem_featured and current_user.plan_details and current_user.plan_details.has_images:
            auth_wp = (blog.wp_user, blog.wp_app_password)
            id_imagem = processar_imagem_featured(idea.title, blog.wp_url, auth_wp)

        response = enviar_para_wordpress(texto_final, idea.title, id_imagem, blog)

        if response and response.status_code in [200, 201]:
            current_user.credits -= 1
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
            
            flash(f"Artigo publicado! 1 crédito debitado (Saldo: {current_user.credits})", "success")
        else:
            flash(f"Erro ao publicar no WordPress. Nenhum crédito foi debitado.", "danger")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro técnico na publicação: {str(e)}", "danger")

    return redirect(url_for('content.ideas'))

# --- 4. POST MANUAL E RELATÓRIOS ---
@content_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    blogs = Blog.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        # Verificação de créditos (Demo ignora)
        if current_user.credits <= 0 and current_user.email != DEMO_EMAIL:
            flash("Você não possui créditos para um post manual.", "warning")
            return redirect(url_for('dashboard.dashboard_view'))

        blog_id = request.form.get('blog_id')
        titulo = request.form.get('title')
        conteudo = request.form.get('content')

        if not blog_id:
            flash("Por favor, selecione um blog.", "warning")
            return render_template('manual_post.html', blogs=blogs)

        blog = db.session.get(Blog, blog_id)

        if blog and blog.user_id == current_user.id:
            # INTERCEPTAÇÃO DEMO
            if current_user.email == DEMO_EMAIL:
                flash("Post manual simulado com sucesso (Modo Demo)!", "success")
                return redirect(url_for('content.post_report'))

            res = enviar_para_wordpress(conteudo, titulo, None, blog)
            
            if res and res.status_code in [200, 201]:
                current_user.consume_credit()
                flash("Post manual publicado com sucesso!", "success")
                return redirect(url_for('content.post_report'))
            else:
                flash("Falha ao enviar para o WordPress. Verifique credenciais.", "danger")
        else:
            flash("Blog não encontrado ou acesso negado.", "danger")
                
    return render_template('manual_post.html', blogs=blogs)

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
    # SEGURANÇA: Não permite que o demo delete ideias (para manter a fila cheia para o próximo)
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: A remoção de ideias está desabilitada para manter o ambiente de teste.', 'warning')
        return redirect(url_for('content.ideas'))

    idea = ContentIdea.query.join(Blog).filter(
        ContentIdea.id == idea_id, 
        Blog.user_id == current_user.id
    ).first_or_404()
    
    db.session.delete(idea)
    db.session.commit()
    flash('Ideia removida.', 'info')
    return redirect(url_for('content.ideas'))

@content_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed_content = None
    
    if request.method == 'POST':
        # Verificação de segurança para Demo
        if current_user.email == DEMO_EMAIL:
            flash("Modo Demo: Simulação de extração e reescrita de conteúdo.", "info")
            processed_content = "Este é um exemplo de conteúdo reescrito pela IA no modo de demonstração. Em uma conta real, extrairíamos o texto da URL fornecida e criaríamos uma versão única para seu blog."
            return render_template('spy_writer.html', processed_content=processed_content)

        wp_url = request.form.get('wp_url')
        try:
            # Extração real (apenas para não-demo)
            raw_text = extrair_texto_da_url(wp_url)
            if raw_text:
                # Chama a IA para reescrever
                prompt = f"Reescreva o seguinte artigo de forma original e otimizada para SEO: {raw_text[:3000]}"
                processed_content = generate_text(prompt)
            else:
                flash("Não foi possível extrair texto desta URL. Verifique se o site permite raspagem.", "warning")
        except Exception as e:
            flash(f"Erro ao processar URL: {str(e)}", "danger")
            
    return render_template('spy_writer.html', processed_content=processed_content)