from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea, PostLog
import requests
from requests.auth import HTTPBasicAuth
import os
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime
from utils.scrapers import extrair_texto_da_url
from utils.ai_logic import preparar_contexto_brainstorm

load_dotenv()

content_bp = Blueprint('content', __name__)

def get_groq_client():
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- CONSTANTE PARA O USUÁRIO DEMO ---
DEMO_EMAIL = 'demo@wpautoblog.com.br'

@content_bp.route('/ideas')
@login_required
def ideas():
    site_id = request.args.get('site_id')
    query = ContentIdea.query.join(Blog).filter(Blog.user_id == current_user.id, ContentIdea.is_posted == False)
    
    if site_id and site_id.isdigit():
        query = query.filter(ContentIdea.blog_id == int(site_id))
        
    ideas_list = query.order_by(ContentIdea.created_at.desc()).all()
    return render_template('ideas.html', ideas=ideas_list)

@content_bp.route('/generate-ideas', methods=['POST'])
@login_required
def generate_ideas():
    # 1. Verificação de segurança: O usuário tem sites?
    if not current_user.sites:
        flash('Você precisa cadastrar pelo menos um site antes de gerar ideias.', 'info')
        return redirect(url_for('sites.manage_sites'))

    site_id = request.form.get('site_id')
    
    # 2. Se não veio site_id no formulário (ex: clicou no botão geral), 
    # pega o primeiro site do usuário como padrão
    if not site_id:
        site_id = current_user.sites[0].id
        
    if current_user.email == DEMO_EMAIL:
        ideias_existentes = ContentIdea.query.join(Blog).filter(Blog.user_id == current_user.id).count()
        if ideias_existentes > 20:
            flash('Modo Demo: Limite de ideias atingido.', 'warning')
            return redirect(url_for('content.ideas'))

    site_id = request.form.get('site_id')
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first()
    
    if not site or not site.macro_themes:
        flash('Configure os Macro Temas primeiro!', 'danger')
        return redirect(url_for('sites.manage_sites'))
    
    contexto = preparar_contexto_brainstorm(site)

    try:
        groq_client = get_groq_client()
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Gerador de títulos SEO. Saída um por linha."},
                {"role": "user", "content": f"CONTEXTO: {contexto}\n\nGere 10 títulos."}
            ]
        )
        respostas = completion.choices[0].message.content.strip().split('\n')
        for titulo in respostas:
            if titulo.strip():
                db.session.add(ContentIdea(blog_id=site.id, title=titulo.strip()[:250]))
        db.session.commit()
        flash(f'Ideias geradas para {site.site_name}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro: {str(e)}', 'danger')

    return redirect(url_for('content.ideas', site_id=site.id))

@content_bp.route('/publish-idea/<int:idea_id>')
@login_required
def publish_idea(idea_id):
    if not current_user.pode_postar_automatico():
        flash("Limite atingido. Verifique seus créditos ou plano.", "warning")
        return redirect(url_for('content.ideas'))
    
    idea = ContentIdea.query.get_or_404(idea_id)
    site = Blog.query.get_or_404(idea.blog_id)
    postagem_sucesso = False 

    try:
        groq_client = get_groq_client()
        master_prompt = site.master_prompt or "Você é um redator especialista em SEO."
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": master_prompt},
                {"role": "user", "content": f"Escreva um artigo HTML para: '{idea.title}'."}
            ]
        )
        artigo_html = completion.choices[0].message.content

        wp_api_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        response = requests.post(
            wp_api_url,
            json={"title": idea.title, "content": artigo_html, "status": "publish"},
            auth=HTTPBasicAuth(site.wp_user, site.wp_app_password),
            timeout=30
        )

        if response.status_code == 201:
            data = response.json()
            db.session.add(PostLog(blog_id=site.id, title=idea.title, content=artigo_html, 
                                   wp_post_id=data.get('id'), post_url=data.get('link'), status='Publicado'))
            idea.is_posted = True
            postagem_sucesso = True 
    except Exception as e:
        flash(f'Erro na automação: {str(e)}', 'danger')
    
    if postagem_sucesso:
        current_user.credits -= 1
        db.session.commit()
        flash(f"Publicado! Créditos: {current_user.credits}", "success")
    else:
        db.session.rollback()

    return redirect(url_for('content.ideas', site_id=site.id))

@content_bp.route('/post-report')
@login_required
def post_report():
    site_id = request.args.get('site_id')
    query = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id)
    if site_id and site_id.isdigit():
        query = query.filter(PostLog.blog_id == int(site_id))
    logs = query.order_by(PostLog.posted_at.desc()).all()
    return render_template('post_report.html', logs=logs)

@content_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed_content = None
    if request.method == 'POST':
        url = request.form.get('url')
        texto = extrair_texto_da_url(url)
        try:
            groq_client = get_groq_client()
            res = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": f"Reescreva em HTML: {texto[:4000]}"}]
            )
            processed_content = {'title': "Nova Ideia", 'text': res.choices[0].message.content}
        except: flash("Erro no Espião.", "danger")
    return render_template('spy_writer.html', user=current_user, processed_content=processed_content)

@content_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    if request.method == 'POST':
        site_id = request.form.get('site_id')
        title = request.form.get('title')
        content = request.form.get('content')
        
        # --- CORREÇÃO AQUI ---
        if not site_id:
            flash('Erro: Você precisa selecionar um site antes de postar.', 'error')
            return redirect(url_for('content.manual_post'))
        
        try:
            # Garante que o ID seja um número válido antes de consultar o banco
            site_id_int = int(site_id)
            site = Blog.query.filter_by(id=site_id_int, user_id=current_user.id).first()
        except (ValueError, TypeError):
            flash('Erro: ID do site inválido.', 'error')
            return redirect(url_for('content.manual_post'))
        # ----------------------

        if not site:
            flash('Site não encontrado.', 'danger')
            return redirect(url_for('content.manual_post'))

        try:
            wp_api_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
            response = requests.post(wp_api_url, 
                json={"title": title, "content": content, "status": "publish"},
                auth=HTTPBasicAuth(site.wp_user, site.wp_app_password), 
                timeout=30)

            if response.status_code == 201:
                data = response.json()
                novo_log = PostLog(blog_id=site.id, title=title, content=content, 
                                   wp_post_id=data.get('id'), post_url=data.get('link'), status='Publicado')
                db.session.add(novo_log)
                db.session.commit()
                flash('Postagem manual realizada!', 'success')
                return redirect(url_for('content.post_report')) # Note o prefixo content aqui também
            else:
                flash(f'Erro no WordPress: {response.status_code}', 'danger')
        except Exception as e:
            flash(f'Erro: {str(e)}', 'danger')
            
    return render_template('manual_post.html', user=current_user)

@content_bp.route('/delete-idea/<int:idea_id>', methods=['POST'])
@login_required
def delete_idea(idea_id):
    # Busca a ideia garantindo que ela pertence a um blog do usuário atual
    idea = ContentIdea.query.join(Blog).filter(
        ContentIdea.id == idea_id, 
        Blog.user_id == current_user.id
    ).first_or_404()
    
    blog_id = idea.blog_id
    db.session.delete(idea)
    db.session.commit()
    
    flash('Ideia removida.', 'info')
    return redirect(url_for('content.ideas', site_id=blog_id))