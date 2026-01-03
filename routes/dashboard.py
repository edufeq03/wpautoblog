from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea, PostLog, ContentSource
import requests
from requests.auth import HTTPBasicAuth
import os, re
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime
from utils.scrapers import extrair_texto_da_url
from utils.ai_logic import preparar_contexto_brainstorm

# Carregar variáveis de ambiente
load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard_view():
    # 1. Pegamos o saldo de créditos do usuário (ajuste conforme seu modelo User)
    saldo_atual = current_user.credits if hasattr(current_user, 'credits') else 0
    
    # 2. Pegamos os últimos 5 logs de postagem do usuário para a tabela
    # Fizemos um join com Blog para garantir que pegamos apenas os logs deste usuário
    logs_recentes = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id)\
        .order_by(PostLog.posted_at.desc()).limit(5).all()

    # 3. Contagem de posts feitos hoje
    hoje = datetime.utcnow().date()
    posts_hoje = PostLog.query.join(Blog).filter(
        Blog.user_id == current_user.id,
        PostLog.posted_at >= hoje
    ).count()

    return render_template('dashboard.html', 
                           user=current_user, 
                           saldo=saldo_atual, 
                           logs=logs_recentes,
                           posts_hoje=posts_hoje)

@dashboard_bp.route('/ideas')
@login_required
def ideas():
    site_id = request.args.get('site_id')
    query = ContentIdea.query.join(Blog).filter(Blog.user_id == current_user.id, ContentIdea.is_posted == False)
    
    if site_id and site_id.isdigit():
        query = query.filter(ContentIdea.blog_id == int(site_id))
        
    ideas = query.order_by(ContentIdea.created_at.desc()).all()
    return render_template('ideas.html', ideas=ideas)

@dashboard_bp.route('/generate-ideas', methods=['POST'])
@login_required
def generate_ideas():
    site_id = request.form.get('site_id')
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first() if site_id else \
           Blog.query.filter_by(user_id=current_user.id).first()

    if not site or not site.macro_themes:
        flash('Configure os Macro Temas nas configurações do site primeiro!', 'danger')
        return redirect(url_for('dashboard.manage_sites'))
    
    contexto_enriquecido = preparar_contexto_brainstorm(site)

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "Você é um gerador de títulos SEO. "
                        "Sua saída deve conter APENAS os títulos, um por linha. "
                        "PROIBIDO incluir introduções, conclusões, explicações ou numeração. "
                        "PROIBIDO usar aspas ou negritos nos títulos."
                    )
                },
                {
                    "role": "user", 
                    "content": (
                        f"CONTEXTO: {contexto_enriquecido}\n\n"
                        "Gere 10 títulos virais seguindo as regras rigorosamente."
                    )
                }
            ],
            temperature=0.8,
        )

        respostas = completion.choices[0].message.content.strip().split('\n')
        for titulo in respostas:
            if titulo.strip():
                nova_ideia = ContentIdea(blog_id=site.id, title=titulo.strip()[:250], is_posted=False)
                db.session.add(nova_ideia)
        
        db.session.commit()
        flash(f'Novas ideias geradas para {site.site_name}!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro no Groq: {str(e)}', 'danger')

    return redirect(url_for('dashboard.ideas', site_id=site.id))

@dashboard_bp.route('/publish-idea/<int:idea_id>')
@login_required
def publish_idea(idea_id):
    idea = ContentIdea.query.get_or_404(idea_id)
    site = Blog.query.get_or_404(idea.blog_id)

    if site.user_id != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard.ideas'))

    try:
        master_prompt = site.master_prompt or "Você é um redator especialista em SEO."
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": master_prompt},
                {"role": "user", "content": f"Escreva um artigo completo para: '{idea.title}'. Use tags HTML (h2, p, ul, li)."}
            ],
            temperature=0.7,
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
            novo_log = PostLog(blog_id=site.id, title=idea.title, content=artigo_html, wp_post_id=data.get('id'), post_url=data.get('link'), status='Publicado')
            idea.is_posted = True
            db.session.add(novo_log)
            db.session.commit()
            flash(f'Artigo publicado com sucesso!', 'success')
        else:
            flash(f'Erro no WordPress: {response.status_code}', 'danger')

    except Exception as e:
        flash(f'Erro na automação: {str(e)}', 'danger')

    return redirect(url_for('dashboard.ideas', site_id=site.id))

@dashboard_bp.route('/post-report')
@login_required
def post_report():
    site_id = request.args.get('site_id')
    query = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id)
    if site_id and site_id.isdigit():
        query = query.filter(PostLog.blog_id == int(site_id))
    logs = query.order_by(PostLog.posted_at.desc()).all()
    return render_template('post_report.html', logs=logs)

@dashboard_bp.route('/manage-sites')
@login_required
def manage_sites():
    return render_template('manage_sites.html', user=current_user)

@dashboard_bp.route('/add-site', methods=['POST'])
@login_required
def add_site():
    if not current_user.can_add_site():
        flash('Limite de sites atingido.', 'error')
        return redirect(url_for('dashboard.pricing'))

    new_blog = Blog(
        user_id=current_user.id,
        site_name=request.form.get('site_name'),
        wp_url=request.form.get('wp_url').strip('/'),
        wp_user=request.form.get('wp_user'),
        wp_app_password=request.form.get('wp_app_password')
    )
    db.session.add(new_blog)
    db.session.commit()
    flash('Site conectado!', 'success')
    return redirect(url_for('dashboard.manage_sites'))

@dashboard_bp.route('/delete-idea/<int:idea_id>', methods=['POST'])
@login_required
def delete_idea(idea_id):
    idea = ContentIdea.query.join(Blog).filter(ContentIdea.id == idea_id, Blog.user_id == current_user.id).first_or_404()
    db.session.delete(idea)
    db.session.commit()
    flash('Ideia removida.', 'info')
    return redirect(url_for('dashboard.ideas'))

@dashboard_bp.route('/delete-site/<int:site_id>', methods=['POST'])
@login_required
def delete_site(site_id):
    site = Blog.query.get_or_404(site_id)
    if site.user_id == current_user.id:
        db.session.delete(site)
        db.session.commit()
        flash('Site removido.', 'success')
    return redirect(url_for('dashboard.manage_sites'))

@dashboard_bp.route('/test-post/<int:site_id>')
@login_required
def test_post(site_id):
    site = Blog.query.get_or_404(site_id)
    wp_endpoint = f"{site.wp_url}/wp-json/wp/v2/posts"
    try:
        response = requests.post(wp_endpoint, json={"title": "Teste", "content": "OK", "status": "publish"},
            auth=HTTPBasicAuth(site.wp_user, site.wp_app_password), timeout=10)
        flash("Conexão OK!" if response.status_code == 201 else "Erro de Conexão", "success" if response.status_code == 201 else "error")
    except Exception as e:
        flash(f"Erro: {str(e)}", "error")
    return redirect(url_for('dashboard.manage_sites'))

@dashboard_bp.route('/update-prompt/<int:site_id>', methods=['POST'])
@login_required
def update_prompt(site_id):
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    site.master_prompt = request.form.get('master_prompt')
    site.macro_themes = request.form.get('macro_themes') 
    db.session.commit()
    flash('Configurações atualizadas!', 'success')
    return redirect(url_for('dashboard.manage_sites'))

@dashboard_bp.route('/general-config')
@login_required
def general_config():
    return render_template('general_config.html', user=current_user)

@dashboard_bp.route('/pricing')
@login_required
def pricing():
    return render_template('pricing.html', user=current_user)

@dashboard_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    if request.method == 'POST':
        site_id = request.form.get('site_id')
        title = request.form.get('title')
        content = request.form.get('content')
        
        site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()

        try:
            # Envio para WordPress
            wp_api_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
            response = requests.post(
                wp_api_url,
                json={"title": title, "content": content, "status": "publish"},
                auth=HTTPBasicAuth(site.wp_user, site.wp_app_password),
                timeout=30
            )

            if response.status_code == 201:
                data = response.json()
                # Registra no log para aparecer no Dashboard/Relatórios
                novo_log = PostLog(
                    blog_id=site.id,
                    title=title,
                    content=content,
                    wp_post_id=data.get('id'),
                    post_url=data.get('link'),
                    status='Publicado'
                )
                db.session.add(novo_log)
                db.session.commit()
                flash('Postagem manual realizada com sucesso!', 'success')
                return redirect(url_for('dashboard.post_report'))
            else:
                flash(f'Erro no WordPress: {response.status_code}', 'danger')

        except Exception as e:
            flash(f'Erro ao conectar com o site: {str(e)}', 'danger')
            
    return render_template('manual_post.html', user=current_user)

@dashboard_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    """
    Rota responsável por receber uma URL, extrair seu conteúdo real
    e utilizar IA para transformar em um post de blog formatado.
    """
    processed_content = None
    
    if request.method == 'POST':
        url = request.form.get('url')
        
        # 1. Chamada ao módulo de extração (Scraper)
        # Esta função deve estar definida no mesmo arquivo ou importada
        conteudo_bruto = extrair_texto_da_url(url)
        
        # 2. Lógica de Fallback Modular:
        # Se o scraper falhar (ex: erro 403), enviamos apenas a URL para a IA
        if conteudo_bruto:
            contexto_ia = f"CONTEÚDO REAL DA PÁGINA: {conteudo_bruto}"
            print(f"Sucesso na raspagem: {len(conteudo_bruto)} caracteres extraídos.")
        else:
            contexto_ia = f"URL DE REFERÊNCIA (Acesso direto bloqueado): {url}"
            flash("O site bloqueou a leitura automática, a IA usará apenas a URL como base.", "warning")

        try:
            # 3. Processamento com a Inteligência Artificial
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "Você é um Especialista em SEO e Copywriting. "
                            "Sua tarefa é criar um artigo original em HTML (h2, p, ul). "
                            "Se eu fornecer o CONTEÚDO REAL, use-o como base fiel. "
                            "Se eu fornecer apenas a URL, imagine o conteúdo baseado no tema do link. "
                            "Saída apenas em HTML, sem tags body ou head."
                        )
                    },
                    {"role": "user", "content": f"Referência para processar: {contexto_ia}"}
                ],
                temperature=0.6 # Equilíbrio entre criatividade e fidelidade aos fatos
            )
            
            conteudo_gerado = response.choices[0].message.content
            
            # 4. Estruturação Modular do Resultado para o Template
            # O título é gerado de forma simples via Python para garantir estabilidade
            processed_content = {
                'title': f"Insight: {url.split('/')[-1].replace('-', ' ').replace('/', '').title()}",
                'text': conteudo_gerado
            }
            
        except Exception as e:
            print(f"Erro na API de IA: {e}")
            flash("Ocorreu um erro ao gerar o conteúdo com a IA.", "danger")

    # Retorna sempre para o mesmo template, com ou sem conteúdo processado
    return render_template(
        'spy_writer.html', 
        user=current_user, 
        processed_content=processed_content
    )

@dashboard_bp.route('/radar')
@login_required
def radar():
    site_id = request.args.get('site_id')
    
    # Busca fontes vinculadas aos blogs do utilizador logado
    query = ContentSource.query.join(Blog).filter(Blog.user_id == current_user.id)
    
    if site_id and site_id.isdigit():
        query = query.filter(ContentSource.blog_id == int(site_id))
    
    fontes = query.order_by(ContentSource.created_at.desc()).all()
    
    return render_template('radar.html', user=current_user, fontes=fontes)

# Rota adicional para apagar fontes do Radar
@dashboard_bp.route('/delete-source/<int:source_id>', methods=['POST'])
@login_required
def delete_source(source_id):
    fonte = ContentSource.query.join(Blog).filter(
        ContentSource.id == source_id, 
        Blog.user_id == current_user.id
    ).first_or_404()
    
    db.session.delete(fonte)
    db.session.commit()
    flash('Fonte removida do radar.', 'info')
    return redirect(url_for('dashboard.radar'))

@dashboard_bp.route('/add-source', methods=['POST'])
@login_required
def add_source():
    url = request.form.get('url').strip()
    site_id = request.form.get('site_id')
    
    # 1. Validação de Segurança
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()

    # 2. Lógica de Identificação Automática
    if "youtube.com" in url or "youtu.be" in url:
        source_type = 'youtube'
    else:
        source_type = 'blog' # Padroniza como blog para qualquer outra URL

    try:
        # 3. Salvar no Banco
        nova_fonte = ContentSource(
            blog_id=site.id,
            source_url=url,
            source_type=source_type,
            is_active=True
        )
        db.session.add(nova_fonte)
        db.session.commit()
        
        flash(f'Fonte adicionada ao Radar com sucesso! Tipo identificado: {source_type.capitalize()}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar fonte: {str(e)}', 'danger')

    return redirect(url_for('dashboard.radar', site_id=site.id))

@dashboard_bp.route('/sync-radar')
@login_required
def sync_radar():
    from models import ContentSource, CapturedContent # Certifique-se de que os nomes estão corretos
    
    # 1. Busca todas as fontes do utilizador logado
    fontes = ContentSource.query.join(Blog).filter(Blog.user_id == current_user.id).all()
    
    if not fontes:
        flash("Nenhuma fonte encontrada no Radar. Cadastre uma primeiro!", "warning")
        return redirect(url_for('dashboard.radar'))

    contador = 0
    for fonte in fontes:
        # 2. Chama o nosso Scraper (que já configurámos com BeautifulSoup)
        texto_real = extrair_texto_da_url(fonte.source_url)
        
        if texto_real:
            try:
                # 3. IA gera um resumo para a "Memória"
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "Resume este post em 3 pontos-chave para SEO."},
                        {"role": "user", "content": texto_real[:4000]}
                    ]
                )
                resumo = response.choices[0].message.content
                
                # 4. Salva na tabela CapturedContent
                nova_captura = CapturedContent(
                    source_id=fonte.id,
                    site_id=fonte.blog_id, # Assumindo que a fonte está ligada a um site
                    url=fonte.source_url,
                    title=f"Insight de {fonte.source_url.split('/')[-2]}",
                    summary=resumo
                )
                db.session.add(nova_captura)
                contador += 1
            except Exception as e:
                print(f"Erro ao processar fonte {fonte.source_url}: {e}")

    db.session.commit()
    flash(f"Sucesso! {contador} fontes do Radar foram lidas e resumidas.", "success")
    return redirect(url_for('dashboard.radar'))