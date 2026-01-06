from models import db, Blog, PostLog
from datetime import datetime
import pytz
import requests
from requests.auth import HTTPBasicAuth

def check_and_post_all_sites(app):
    """Varre o banco de dados e dispara postagens nos horários agendados de cada site."""
    with app.app_context():
        # Debug de início de varredura
        print(f"[{datetime.now().strftime('%d/%m %H:%M:%S')}] Iniciando varredura global...")

        sites = Blog.query.all()

        for site in sites:
            # 1. Ajusta o fuso horário específico deste site
            tz_name = site.timezone or 'America/Sao_Paulo'
            try:
                tz = pytz.timezone(tz_name)
            except Exception:
                tz = pytz.timezone('America/Sao_Paulo')
            
            # 2. Pega a hora exata NAQUELE fuso
            now_in_site_tz = datetime.now(tz)
            current_time_str = now_in_site_tz.strftime('%H:%M')
            
            # Debug detalhado por site
            print(f"| Site: {site.site_name.ljust(20)} | Fuso: {tz_name.ljust(20)} | Agora: {current_time_str} | Alvo: {site.schedule_time} |")

            # 3. Verifica se o horário coincide
            if site.schedule_time == current_time_str:
                
                # 4. Validação de limite diário (Data do fuso do site)
                today_site = now_in_site_tz.date()
                today_posts = PostLog.query.filter(
                    PostLog.blog_id == site.id,
                    db.func.date(PostLog.posted_at) == today_site,
                    PostLog.status == 'Publicado'
                ).count()

                if today_posts < (site.posts_per_day or 1):
                    execute_auto_post(site, app)
                else:
                    print(f"   [AVISO] Limite diário já atingido para {site.site_name}")

def execute_auto_post(site, app):
    """Gera o conteúdo e publica no WordPress."""
    try:
        # Simulação de geração de conteúdo (Aqui entra sua lógica de IA)
        generated_title = f"Post Automático: {site.site_name}"
        generated_content = f"Conteúdo gerado para os temas: {site.macro_themes}"

        wp_endpoint = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        auth = HTTPBasicAuth(site.wp_user, site.wp_app_password)
        
        payload = {
            "title": generated_title,
            "content": generated_content,
            "status": site.post_status or "publish"
        }

        response = requests.post(wp_endpoint, json=payload, auth=auth, timeout=30)

        if response.status_code == 201:
            print(f"✅ [SUCESSO] Postado em: {site.site_name}")
            
            new_log = PostLog(
                blog_id=site.id,
                title=generated_title,
                status='Publicado',
                post_url=response.json().get('link')
            )
            db.session.add(new_log)
            db.session.commit()
            
            # Espaço para Evolution API (WhatsApp) futuramente
        else:
            print(f"❌ [ERRO WP] {site.site_name}: Status {response.status_code}")

    except Exception as e:
        print(f"💥 [ERRO CRÍTICO] {site.site_name}: {str(e)}")