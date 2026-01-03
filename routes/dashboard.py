from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea, PostLog, ContentSource, CapturedContent
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

def get_groq_client():
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

dashboard_bp = Blueprint('dashboard', __name__)

# --- CONSTANTE PARA O USUÁRIO DEMO ---
DEMO_EMAIL = 'demo@wpautoblog.com.br'

@dashboard_bp.route('/dashboard')
@login_required
def dashboard_view():
    limites = current_user.get_plan_limits()
    saldo_atual = current_user.credits if hasattr(current_user, 'credits') else 0
    
    logs_recentes = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id)\
        .order_by(PostLog.posted_at.desc()).limit(5).all()

    # Contagem de posts hoje (Exemplo de lógica)
    hoje = datetime.utcnow().date()
    posts_hoje = PostLog.query.join(Blog).filter(
        Blog.user_id == current_user.id,
        db.func.date(PostLog.posted_at) == hoje
    ).count()

    return render_template('dashboard.html', 
                           user=current_user, 
                           limite_posts=limites['posts_por_dia'],
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
    # TRAVA DEMO: Limitar geração excessiva na conta demo (Opcional, mas recomendado)
    if current_user.email == DEMO_EMAIL:
        ideias_existentes = ContentIdea.query.join(Blog).filter(Blog.user_id == current_user.id).count()
        if ideias_existentes > 20:
            flash('Modo Demo: Limite de ideias atingido para demonstração.', 'warning')
            return redirect(url_for('dashboard.ideas'))

    site_id = request.form.get('site_id')
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first() if site_id else \
           Blog.query.filter_by(user_id=current_user.id).first()

    if not site or not site.macro_themes:
        flash('Configure os Macro Temas nas configurações do site primeiro!', 'danger')
        return redirect(url_for('dashboard.manage_sites'))
    
    contexto_enriquecido = preparar_contexto_brainstorm(site)

    try:
        groq_client = get_groq_client()
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Você é um gerador de títulos SEO. Saída um por linha, sem aspas ou números."},
                {"role": "user", "content": f"CONTEXTO: {contexto_enriquecido}\n\nGere 10 títulos virais."}
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
        flash(f'Erro na geração: {str(e)}', 'danger')

    return redirect(url_for('dashboard.ideas', site_id=site.id))

@dashboard_bp.route('/publish-idea/<int:idea_id>')
@login_required
def publish_idea(idea_id):
    print(f">>> Iniciando publicação da ideia {idea_id}")
    
    if not current_user.pode_postar_automatico():
        print(f">>> Bloqueado: Usuário {current_user.email} sem créditos ou limite atingido.")
        flash("Você atingiu o limite de postagens automáticas.", "warning")
        return redirect(url_for('dashboard.ideas'))
    
    idea = ContentIdea.query.get_or_404(idea_id)
    site = Blog.query.get_or_404(idea.blog_id)

    if site.user_id != current_user.id:
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard.ideas'))

    postagem_sucesso = False 

    try:
        print(f">>> Gerando conteúdo com IA para: {idea.title}")
        groq_client = get_groq_client()
        master_prompt = site.master_prompt or "Você é um redator especialista em SEO."
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": master_prompt},
                {"role": "user", "content": f"Escreva um artigo completo para: '{idea.title}'. Use tags HTML."}
            ],
            temperature=0.7,
        )
        artigo_html = completion.choices[0].message.content

        print(f">>> Enviando para WordPress: {site.wp_url}")
        wp_api_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        response = requests.post(
            wp_api_url,
            json={"title": idea.title, "content": artigo_html, "status": "publish"},
            auth=HTTPBasicAuth(site.wp_user, site.wp_app_password),
            timeout=30
        )

        print(f">>> Resposta WordPress: {response.status_code}")
        if response.status_code == 201:
            data = response.json()
            novo_log = PostLog(
                blog_id=site.id, 
                title=idea.title, 
                content=artigo_html, 
                wp_post_id=data.get('id'), 
                post_url=data.get('link'), 
                status='Publicado'
            )
            idea.is_posted = True
            db.session.add(novo_log)
            # Removi o commit daqui para fazer um só no final
            postagem_sucesso = True 
        else:
            print(f">>> Erro WP Detalhes: {response.text}")
            flash(f'Erro no WordPress: {response.status_code}', 'danger')

    except Exception as e:
        print(f">>> ERRO NA AUTOMAÇÃO: {str(e)}")
        flash(f'Erro na automação: {str(e)}', 'danger')
    
    # Processamento de Créditos
    if postagem_sucesso:
        print(f">>> Saldo ANTES: {current_user.credits}")
        try:
            # Deduz o crédito
            current_user.credits -= 1
            # Comita tudo de uma vez (Log, Status da Ideia e Crédito)
            db.session.commit()
            print(f">>> Saldo DEPOIS: {current_user.credits}")
            flash(f"Artigo publicado! Créditos restantes: {current_user.credits}", "success")
        except Exception as e:
            db.session.rollback()
            print(f">>> Erro ao salvar no banco: {e}")
            flash("Erro ao atualizar saldo.", "danger")
    else:
        print(">>> Postagem não teve sucesso, saldo não deduzido.")

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
    # TRAVA DEMO: Impedir que adicionem novos sites na conta demo
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Você não pode adicionar novos sites nesta conta.', 'warning')
        return redirect(url_for('dashboard.manage_sites'))

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
    # TRAVA DEMO: Não deixar apagar as ideias da demo
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: A exclusão de ideias está desabilitada.', 'warning')
        return redirect(url_for('dashboard.ideas'))

    idea = ContentIdea.query.join(Blog).filter(ContentIdea.id == idea_id, Blog.user_id == current_user.id).first_or_404()
    db.session.delete(idea)
    db.session.commit()
    flash('Ideia removida.', 'info')
    return redirect(url_for('dashboard.ideas'))

@dashboard_bp.route('/delete-site/<int:site_id>', methods=['POST'])
@login_required
def delete_site(site_id):
    # TRAVA DEMO: Crucial - Não deixar deletar o site de demonstração
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Você não pode remover o site de demonstração.', 'danger')
        return redirect(url_for('dashboard.manage_sites'))

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
    wp_endpoint = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    
    # Conteúdo formatado para o post de teste
    titulo_teste = "🚀 Teste de Conexão: WP AutoBlog"
    corpo_teste = f"""
    <h2>Conexão Bem-Sucedida!</h2>
    <p>Este post é um teste automático gerado pelo <strong>WP AutoBlog</strong> para o site <em>{site.site_name}</em>.</p>
    <p>Se você está lendo isso, significa que:</p>
    <ul>
        <li>A API REST do seu WordPress está ativa.</li>
        <li>As credenciais de Application Password são válidas.</li>
        <li>O servidor conseguiu estabelecer comunicação com seu blog.</li>
    </ul>
    <p><em>Você pode excluir este post manualmente a qualquer momento.</em></p>
    <hr>
    <p><small>Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</small></p>
    """

    try:
        response = requests.post(
            wp_endpoint, 
            json={
                "title": titulo_teste, 
                "content": corpo_teste, 
                "status": "publish",
                "categories": [] # Opcional: define uma categoria se desejar
            },
            auth=HTTPBasicAuth(site.wp_user, site.wp_app_password), 
            timeout=15
        )
        
        if response.status_code == 201:
            data = response.json()
            link_post = data.get('link')
            flash(f"✅ Conexão estabelecida! O post de teste foi publicado com sucesso.", "success")
            # Opcional: Você pode até enviar o link no flash para o usuário clicar
            print(f"Post de teste publicado em: {link_post}")
        else:
            print(f"Erro WP: {response.text}")
            flash(f"❌ Erro de Conexão (Status {response.status_code}). Verifique as credenciais.", "danger")
            
    except Exception as e:
        flash(f"⚠️ Erro ao tentar conectar: {str(e)}", "danger")
        
    return redirect(url_for('dashboard.manage_sites'))

@dashboard_bp.route('/update-prompt/<int:site_id>', methods=['POST'])
@login_required
def update_prompt(site_id):
    # TRAVA DEMO: Impedir mudança de temas/prompt que alteram o comportamento da demo
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Alteração de prompt e temas desabilitada.', 'warning')
        return redirect(url_for('dashboard.manage_sites'))

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
    return render_template('pricing.html', user=current_user, planos=PLANOS)

PLANOS = {
    'trial': {'nome': 'Plano Trial', 'preco': 'Grátis', 'sites': '1', 'posts': '1', 'espiao': False},
    'pro': {'nome': 'Plano Pro', 'preco': 'R$ 59', 'sites': '2', 'posts': '5', 'espiao': True},
    'vip': {'nome': 'Plano VIP', 'preco': 'R$ 249', 'sites': 'Ilimitados', 'posts': 'Ilimitadas', 'espiao': True}
}

@dashboard_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    if request.method == 'POST':
        
        site_id = request.form.get('site_id')
        title = request.form.get('title')
        content = request.form.get('content')
        site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()

        try:
            wp_api_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
            response = requests.post(wp_api_url, json={"title": title, "content": content, "status": "publish"},
                auth=HTTPBasicAuth(site.wp_user, site.wp_app_password), timeout=30)

            if response.status_code == 201:
                data = response.json()
                novo_log = PostLog(blog_id=site.id, title=title, content=content, wp_post_id=data.get('id'), post_url=data.get('link'), status='Publicado')
                db.session.add(novo_log)
                db.session.commit()
                flash('Postagem manual realizada!', 'success')
                return redirect(url_for('dashboard.post_report'))
            else:
                flash(f'Erro no WordPress: {response.status_code}', 'danger')
        except Exception as e:
            flash(f'Erro: {str(e)}', 'danger')
            
    return render_template('manual_post.html', user=current_user)

@dashboard_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed_content = None
    if request.method == 'POST':
        url = request.form.get('url')
        conteudo_bruto = extrair_texto_da_url(url)
        contexto_ia = f"CONTEÚDO REAL: {conteudo_bruto}" if conteudo_bruto else f"URL: {url}"

        try:
            groq_client = get_groq_client()
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Você é um Especialista em SEO. Crie um artigo original em HTML."},
                    {"role": "user", "content": f"Referência: {contexto_ia}"}
                ],
                temperature=0.6
            )
            processed_content = {'title': "Nova Ideia", 'text': response.choices[0].message.content}
        except Exception as e:
            flash("Erro ao gerar conteúdo.", "danger")

    return render_template('spy_writer.html', user=current_user, processed_content=processed_content)

@dashboard_bp.route('/radar')
@login_required
def radar():
    query = ContentSource.query.join(Blog).filter(Blog.user_id == current_user.id)
    site_id = request.args.get('site_id')
    if site_id and site_id.isdigit():
        query = query.filter(ContentSource.blog_id == int(site_id))
    fontes = query.order_by(ContentSource.created_at.desc()).all()
    return render_template('radar.html', user=current_user, fontes=fontes)

@dashboard_bp.route('/delete-source/<int:source_id>', methods=['POST'])
@login_required
def delete_source(source_id):
    # TRAVA DEMO: Não deixar apagar as fontes do radar na demo
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Exclusão de fontes desabilitada.', 'warning')
        return redirect(url_for('dashboard.radar'))

    fonte = ContentSource.query.join(Blog).filter(ContentSource.id == source_id, Blog.user_id == current_user.id).first_or_404()
    db.session.delete(fonte)
    db.session.commit()
    flash('Fonte removida.', 'info')
    return redirect(url_for('dashboard.radar'))

@dashboard_bp.route('/add-source', methods=['POST'])
@login_required
def add_source():
    # TRAVA DEMO: Evitar poluição do radar demo
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Adição de novas fontes desabilitada.', 'warning')
        return redirect(url_for('dashboard.radar'))

    url = request.form.get('url').strip()
    site_id = request.form.get('site_id')
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    source_type = 'youtube' if "youtube.com" in url or "youtu.be" in url else 'blog'

    nova_fonte = ContentSource(blog_id=site.id, source_url=url, source_type=source_type, is_active=True)
    db.session.add(nova_fonte)
    db.session.commit()
    flash('Fonte adicionada ao Radar!', 'success')
    return redirect(url_for('dashboard.radar'))

@dashboard_bp.route('/sync-radar')
@login_required
def sync_radar():
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Sincronização automática desativada para demonstração.', 'info')
        return redirect(url_for('dashboard.radar'))

    fontes = ContentSource.query.join(Blog).filter(Blog.user_id == current_user.id).all()
    if not fontes:
        flash("Nenhuma fonte encontrada.", "warning")
        return redirect(url_for('dashboard.radar'))

    contador = 0
    for fonte in fontes:
        texto_real = extrair_texto_da_url(fonte.source_url)
        if texto_real:
            try:
                groq_client = get_groq_client()
                response = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "Resume este post em 3 pontos SEO."},
                        {"role": "user", "content": texto_real[:4000]}
                    ]
                )
                nova_captura = CapturedContent(source_id=fonte.id, site_id=fonte.blog_id, url=fonte.source_url, title="Insight", summary=response.choices[0].message.content)
                db.session.add(nova_captura)
                contador += 1
            except: continue

    db.session.commit()
    flash(f"Sucesso! {contador} fontes resumidas.", "success")
    return redirect(url_for('dashboard.radar'))

@dashboard_bp.route('/update-prefs/<int:site_id>', methods=['POST'])
@login_required
def update_prefs(site_id):
    site = Blog.query.get_or_404(site_id)
    
    # Verifica se o site pertence ao usuário logado
    if site.user_id != current_user.id:
        flash("Acesso negado.", "error")
        return redirect(url_for('dashboard.manage_sites'))

    # Coleta os dados do formulário do modal
    site.posts_per_day = request.form.get('posts_per_day', type=int)
    site.schedule_time = request.form.get('schedule_time')
    site.post_status = request.form.get('post_status')
    site.default_category = request.form.get('default_category')

    db.session.commit()
    flash(f"Preferências de {site.site_name} atualizadas com sucesso!", "success")
    return redirect(url_for('dashboard.manage_sites'))