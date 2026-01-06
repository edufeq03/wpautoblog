import requests
from requests.auth import HTTPBasicAuth
from models import db, Blog, PostLog
from datetime import datetime
import pytz

def check_and_post_all_sites(app):
    with app.app_context():
        sites = Blog.query.all()
        print(f"\n--- [VARREDURA {datetime.now().strftime('%H:%M:%S')}] ---")

        for site in sites:
            tz_name = site.timezone or 'America/Sao_Paulo'
            tz = pytz.timezone(tz_name)
            now_in_tz = datetime.now(tz)
            current_time_str = now_in_tz.strftime('%H:%M')
            
            print(f"| Site: {site.site_name[:15].ljust(15)} | Agora: {current_time_str} | Alvo: {site.schedule_time} |")

            if site.schedule_time == current_time_str:
                # Evitar duplicidade no mesmo minuto
                already_posted = PostLog.query.filter(
                    PostLog.blog_id == site.id,
                    db.func.date(PostLog.posted_at) == now_in_tz.date(),
                    PostLog.status == 'Publicado'
                ).filter(db.func.strftime('%H:%M', PostLog.posted_at) == current_time_str).first()

                if not already_posted:
                    execute_auto_post(site, app)

def execute_auto_post(site, app):
    """Gera conteúdo e envia para a REST API do WordPress."""
    try:
        print(f"   🚀 Iniciando postagem real para: {site.site_name}")

        # --- PARTE 1: GERADOR DE CONTEÚDO (MOCK POR ENQUANTO) ---
        # No próximo passo, aqui chamaremos a OpenAI/Gemini
        titulo = f"Inovação em {site.macro_themes.split(',')[0] if site.macro_themes else 'Tecnologia'}"
        conteudo = f"""
        <h2>🚀 Post enviado via WP AutoBlog</h2>
        <p>Este é um teste de integração real.</p>
        <ul>
            <li><b>Site:</b> {site.site_name}</li>
            <li><b>Temas configurados:</b> {site.macro_themes}</li>
            <li><b>Horário do disparo:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</li>
        </ul>
        <p><i>Se você está vendo isso, a conexão entre seu Python e o WordPress está funcionando perfeitamente!</i></p>
        """

        # --- PARTE 2: CONEXÃO COM WP REST API ---
        # Ajusta a URL para o endpoint de posts
        wp_url = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        
        payload = {
            "title": titulo,
            "content": conteudo,
            "status": site.post_status or "publish"
        }

        # Autenticação Basic (User + App Password)
        auth = HTTPBasicAuth(site.wp_user, site.wp_app_password)

        response = requests.post(wp_url, json=payload, auth=auth, timeout=30)

        if response.status_code == 201:
            post_data = response.json()
            print(f"   ✅ SUCESSO! Post publicado: {post_data.get('link')}")
            
            # Registrar no banco para controle
            new_log = PostLog(
                blog_id=site.id,
                title=titulo,
                status='Publicado',
                post_url=post_data.get('link')
            )
            db.session.add(new_log)
            db.session.commit()
        else:
            print(f"   ❌ ERRO WP ({response.status_code}): {response.text}")

    except Exception as e:
        print(f"   💥 ERRO CRÍTICO: {str(e)}")