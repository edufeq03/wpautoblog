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
    # Proteção: Se não houver sites, redireciona para cadastro
    if not current_user.sites:
        flash('Você precisa cadastrar um site antes de gerar ideias.', 'info')
        return redirect(url_for('sites.manage_sites'))

    site_id = request.form.get('site_id')
    
    # Se o ID vier vazio (erro que corrigimos no HTML), tenta pegar o primeiro site do user
    if not site_id:
        site_id = current_user.sites[0].id
    
    try:
        site_id = int(site_id)
        site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first()
    except (ValueError, TypeError):
        flash('ID do site inválido.', 'danger')
        return redirect(url_for('content.ideas'))

    if not site:
        flash('Site não encontrado.', 'danger')
        return redirect(url_for('content.ideas'))

    try:
        client = get_groq_client()
        contexto = preparar_contexto_brainstorm(site)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Você é um especialista em SEO e marketing de conteúdo. Gere 5 ideias de títulos de blog baseados no contexto do usuário. Retorne apenas os títulos, um por linha."},
                {"role": "user", "content": contexto}
            ],
            model="llama-3.1-70b-versatile",
        )

        titulos = chat_completion.choices[0].message.content.strip().split('\n')
        
        for t in titulos:
            if t.strip():
                # Remove numerações automáticas da IA (ex: "1. Título")
                titulo_limpo = t.split('. ', 1)[-1] if '. ' in t[:4] else t
                nova_ideia = ContentIdea(blog_id=site.id, title=titulo_limpo.strip())
                db.session.add(nova_ideia)
        
        db.session.commit()
        flash(f'{len(titulos)} novas ideias geradas para {site.site_name}!', 'success')
        
    except Exception as e:
        flash(f'Erro na IA: {str(e)}', 'danger')

    return redirect(url_for('content.ideas', site_id=site_id))

@content_bp.route('/publish-idea/<int:idea_id>')
@login_required
def publish_idea(idea_id):
    idea = ContentIdea.query.get_or_404(idea_id)
    site = idea.blog
    
    # Verifica se o site pertence ao usuário
    if site.user_id != current_user.id:
        flash('Acesso negado.', 'danger')
        return redirect(url_for('content.ideas'))

    try:
        client = get_groq_client()
        prompt_sistema = site.master_prompt or "Você é um redator profissional. Escreva um artigo de blog otimizado para SEO."
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Escreva um artigo completo sobre: {idea.title}. Use formatação HTML (h2, p, strong)."}
            ],
            model="llama-3.1-70b-versatile",
        )

        content = chat_completion.choices[0].message.content
        
        # Publicar no WordPress
        wp_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        response = requests.post(
            wp_url,
            json={
                "title": idea.title,
                "content": content,
                "status": site.post_status or "publish",
                "categories": [site.default_category] if site.default_category else []
            },
            auth=HTTPBasicAuth(site.wp_user, site.wp_app_password),
            timeout=30
        )

        if response.status_code == 201:
            data = response.json()
            
            # --- AJUSTE PARA EVITAR O INTEGRITY ERROR ---
            # Forçamos a captura do ID do blog antes do log
            blog_id_fix = site.id 
            
            novo_log = PostLog(
                blog_id=blog_id_fix, 
                title=idea.title, 
                content=content, 
                wp_post_id=data.get('id'), 
                post_url=data.get('link'), 
                status='Publicado'
            )
            
            idea.is_posted = True
            db.session.add(novo_log)
            db.session.commit()
            
            flash('Conteúdo publicado com sucesso!', 'success')
            return redirect(url_for('content.post_report'))
        else:
            flash(f'Erro WordPress ({response.status_code}): {response.text}', 'danger')
            
    except Exception as e:
        flash(f'Erro no processo: {str(e)}', 'danger')

    return redirect(url_for('content.ideas'))

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
        try:
            texto_extraido = extrair_texto_da_url(url)
            client = get_groq_client()
            
            completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Você é um redator espião. Resuma e reescreva o conteúdo fornecido em um novo artigo de blog original e otimizado."},
                    {"role": "user", "content": texto_extraido[:8000]} # Limite de contexto
                ],
                model="llama-3.1-70b-versatile",
            )
            processed_content = {
                "title": "Novo Artigo Inspirado",
                "text": completion.choices[0].message.content
            }
        except Exception as e:
            flash(f"Erro ao processar URL: {str(e)}", "danger")

    return render_template('spy_writer.html', processed_content=processed_content)

@content_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    if request.method == 'POST':
        site_id = request.form.get('site_id')
        title = request.form.get('title')
        content = request.form.get('content')

        if not site_id:
            flash('Por favor, selecione um site.', 'error')
            return redirect(url_for('content.manual_post'))

        try:
            site = Blog.query.filter_by(id=int(site_id), user_id=current_user.id).first()
            if not site:
                flash('Site não encontrado.', 'danger')
                return redirect(url_for('content.manual_post'))

            wp_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
            response = requests.post(
                wp_url,
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
                return redirect(url_for('content.post_report'))
            else:
                flash(f'Erro no WordPress: {response.status_code}', 'danger')
        except Exception as e:
            flash(f'Erro: {str(e)}', 'danger')
            
    return render_template('manual_post.html')

@content_bp.route('/delete-idea/<int:idea_id>', methods=['POST'])
@login_required
def delete_idea(idea_id):
    idea = ContentIdea.query.join(Blog).filter(
        ContentIdea.id == idea_id, 
        Blog.user_id == current_user.id
    ).first_or_404()
    
    db.session.delete(idea)
    db.session.commit()
    flash('Ideia removida com sucesso.', 'success')
    return redirect(url_for('content.ideas'))