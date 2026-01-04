from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea, PostLog
import requests
from requests.auth import HTTPBasicAuth
import os
from datetime import datetime

# Importando as funções centralizadas do seu novo serviço de IA
from services.ai_service import generate_text, generate_image
from utils.scrapers import extrair_texto_da_url
from utils.ai_logic import preparar_contexto_brainstorm

content_bp = Blueprint('content', __name__)

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
    if not current_user.sites:
        flash('Você precisa cadastrar pelo menos um site antes de gerar ideias.', 'info')
        return redirect(url_for('sites.manage_sites'))

    site_id = request.form.get('site_id')
    if not site_id:
        site_id = current_user.sites[0].id
        
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first()
    
    if not site or not site.macro_themes:
        flash('Configure os Macro Temas primeiro!', 'danger')
        return redirect(url_for('sites.manage_sites'))
    
    contexto = preparar_contexto_brainstorm(site)

    try:
        # Usando a função centralizada para gerar títulos (quick=True para o modelo 8b)
        resposta = generate_text(
            prompt=f"CONTEXTO: {contexto}\n\nGere 10 títulos de artigos otimizados para SEO.",
            system_prompt="Você é um especialista em SEO. Gere apenas os títulos, um por linha, sem números ou aspas.",
            quick=True
        )

        if resposta:
            titulos = resposta.strip().split('\n')
            for t in titulos:
                if t.strip():
                    # Limpeza simples caso a IA coloque números no início
                    titulo_limpo = t.split('. ', 1)[-1] if '. ' in t[:4] else t
                    db.session.add(ContentIdea(blog_id=site.id, title=titulo_limpo.strip()[:250]))
            
            db.session.commit()
            flash(f'Ideias geradas para {site.site_name}!', 'success')
        else:
            flash('A IA não retornou sugestões.', 'warning')

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao gerar ideias: {e}")
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
        master_prompt = site.master_prompt or "Você é um redator especialista em SEO."
        
        # Gerando o artigo completo usando o modelo mais potente (quick=False)
        artigo_html = generate_text(
            prompt=f"Escreva um artigo completo em HTML sobre: '{idea.title}'.",
            system_prompt=master_prompt,
            quick=False
        )

        if artigo_html:
            wp_api_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
            response = requests.post(
                wp_api_url,
                json={"title": idea.title, "content": artigo_html, "status": site.post_status or "publish"},
                auth=HTTPBasicAuth(site.wp_user, site.wp_app_password),
                timeout=30
            )

            if response.status_code == 201:
                data = response.json()
                db.session.add(PostLog(blog_id=site.id, title=idea.title, content=artigo_html, 
                                       wp_post_id=data.get('id'), post_url=data.get('link'), status='Publicado'))
                idea.is_posted = True
                postagem_sucesso = True 
        else:
            raise Exception("Falha ao gerar conteúdo com a IA.")

    except Exception as e:
        print(f"Erro na publicação automática: {e}")
        flash(f'Erro na automação: {str(e)}', 'danger')
    
    if postagem_sucesso:
        current_user.credits -= 1
        db.session.commit()
        flash(f"Publicado! Créditos restantes: {current_user.credits}", "success")
    else:
        db.session.rollback()

    return redirect(url_for('content.ideas', site_id=site.id))

@content_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed_content = None
    if request.method == 'POST':
        url = request.form.get('url')
        try:
            texto_extraido = extrair_texto_da_url(url)
            
            if not texto_extraido:
                flash("Não foi possível extrair conteúdo desta URL.", "warning")
                return render_template('spy_writer.html', processed_content=None)

            # Usando a função centralizada com correção de aspas na mensagem de flash
            novo_texto = generate_text(
                prompt=f"Reescreva este conteúdo em um novo artigo original e SEO: {texto_extraido[:12000]}",
                system_prompt="Você é um redator espião. Transforme o conteúdo em um artigo de blog profissional usando HTML.",
                quick=False 
            )

            if novo_texto:
                processed_content = {
                    "title": "Novo Artigo Inspirado",
                    "text": novo_texto
                }
                flash('Conteúdo "espiado" e reescrito com sucesso!', 'success')
            else:
                flash("A IA falhou ao processar o texto.", "danger")

        except Exception as e:
            print(f"Erro no Spy Writer: {e}")
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
            flash('Selecione um site antes de postar.', 'error')
            return redirect(url_for('content.manual_post'))
        
        try:
            site = Blog.query.filter_by(id=int(site_id), user_id=current_user.id).first()
            if not site:
                flash('Site não encontrado.', 'danger')
                return redirect(url_for('content.manual_post'))

            wp_api_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
            response = requests.post(wp_api_url, 
                json={"title": title, "content": content, "status": "publish"},
                auth=HTTPBasicAuth(site.wp_user, site.wp_app_password), 
                timeout=30)

            if response.status_code == 201:
                data = response.json()
                db.session.add(PostLog(blog_id=site.id, title=title, content=content, 
                                   wp_post_id=data.get('id'), post_url=data.get('link'), status='Publicado'))
                db.session.commit()
                flash('Postagem manual realizada!', 'success')
                return redirect(url_for('content.post_report'))
            else:
                flash(f'Erro no WordPress: {response.status_code}', 'danger')
        except Exception as e:
            flash(f'Erro: {str(e)}', 'danger')
            
    return render_template('manual_post.html')

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
    
    blog_id = idea.blog_id
    db.session.delete(idea)
    db.session.commit()
    
    flash('Ideia removida.', 'info')
    return redirect(url_for('content.ideas', site_id=blog_id))