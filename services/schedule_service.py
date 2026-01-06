from models import db, Blog, PostLog
from datetime import datetime
import pytz
import requests
from requests.auth import HTTPBasicAuth

def check_and_post_all_sites(app):
    """Varre o banco de dados e dispara postagens nos horários agendados."""
    with app.app_context():
        sites = Blog.query.all()
        print(f"\n--- [VARREDURA {datetime.now().strftime('%H:%M:%S')}] ---")

        for site in sites:
            tz_name = site.timezone or 'America/Sao_Paulo'
            try:
                tz = pytz.timezone(tz_name)
            except:
                tz = pytz.timezone('America/Sao_Paulo')
            
            now_in_tz = datetime.now(tz)
            current_time_str = now_in_tz.strftime('%H:%M')
            
            print(f"| Site: {site.site_name[:15].ljust(15)} | Agora: {current_time_str} | Alvo: {site.schedule_time} |")

            if site.schedule_time == current_time_str:
                # Evita postar múltiplas vezes no mesmo minuto
                today_site = now_in_tz.date()
                already_posted = PostLog.query.filter(
                    PostLog.blog_id == site.id,
                    db.func.date(PostLog.posted_at) == today_site,
                    PostLog.title.like('%TESTE%') # Filtro para o nosso teste
                ).first()

                if not already_posted:
                    print(f"   >>> 🚀 GATILHO ATIVADO para {site.site_name}!")
                    execute_auto_post(site, app)
                else:
                    print(f"   [!] Já postado neste minuto. Aguardando próximo ciclo.")

def execute_auto_post(site, app):
    """Gera o conteúdo e envia para a REST API do WordPress de verdade."""
    try:
        # 1. Definição do Conteúdo de Teste
        # Aqui você edita o que vai aparecer no seu WordPress
        titulo_teste = f"POST DE TESTE REAL: {site.site_name} ({datetime.now().strftime('%H:%M')})"
        conteudo_teste = f"""
        <h2>🚀 Integração WP AutoBlog Funcionando!</h2>
        <p>Este post foi gerado automaticamente pelo sistema às {datetime.now().strftime('%H:%M:%S')}.</p>
        <p><b>Temas configurados:</b> {site.macro_themes}</p>
        <p><i>Verificando conexão via REST API...</i></p>
        """

        print(f"   [*] Conectando à API do WordPress: {site.wp_url}")

        # 2. Configuração da API
        # Endpoint padrão do WP para posts
        wp_endpoint = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        
        # Autenticação (Usuário + Senha de Aplicativo)
        auth = HTTPBasicAuth(site.wp_user, site.wp_app_password)
        
        payload = {
            "title": titulo_teste,
            "content": conteudo_teste,
            "status": site.post_status or "publish" # publish ou draft
        }

        # 3. Envio da Requisição
        response = requests.post(wp_endpoint, json=payload, auth=auth, timeout=30)

        # 4. Verificação do Resultado
        if response.status_code == 201:
            link_do_post = response.json().get('link')
            print(f"   ✅ [SUCESSO] Post publicado!")
            print(f"   🔗 LINK: {link_do_post}")
            
            # Salva o log no banco para aparecer no Dashboard
            new_log = PostLog(
                blog_id=site.id,
                title=titulo_teste,
                status='Publicado',
                post_url=link_do_post
            )
            db.session.add(new_log)
            db.session.commit()
        else:
            print(f"   ❌ [ERRO WP] Status: {response.status_code}")
            print(f"   ℹ️ Detalhes: {response.text}")

    except Exception as e:
        print(f"   💥 [ERRO CRÍTICO] Falha na execução: {str(e)}")