from models import db, Blog, PostLog
from datetime import datetime
import pytz
import requests
from requests.auth import HTTPBasicAuth

def check_and_post_all_sites(app):
    """Varre o banco de dados e dispara postagens nos horários agendados."""
    with app.app_context():
        # 1. Busca todos os sites do banco
        sites = Blog.query.all()
        
        # Log de cabeçalho da varredura
        print(f"\n--- [VARREDURA {datetime.now().strftime('%H:%M:%S')}] ---")

        if not sites:
            print("Nenhum site encontrado no banco de dados.")
            return

        # 2. Loop principal: Processa UM por UM
        for site in sites:
            # Define o fuso horário salvo ou usa SP como padrão
            tz_name = site.timezone or 'America/Sao_Paulo'
            try:
                tz = pytz.timezone(tz_name)
            except:
                tz = pytz.timezone('America/Sao_Paulo')
            
            # Calcula a hora agora NESTE fuso horário específico
            now_in_tz = datetime.now(tz)
            current_time_str = now_in_tz.strftime('%H:%M')
            
            # 3. IMPRIME A LINHA DE CADA SITE (O que você quer ver)
            print(f"| Site: {site.site_name[:15].ljust(15)} | Fuso: {tz_name.ljust(20)} | Agora: {current_time_str} | Alvo: {site.schedule_time} |")

            # 4. Verifica se o relógio bateu
            if site.schedule_time == current_time_str:
                
                # Validação de limite diário
                today_site = now_in_tz.date()
                today_posts = PostLog.query.filter(
                    PostLog.blog_id == site.id,
                    db.func.date(PostLog.posted_at) == today_site,
                    PostLog.status == 'Publicado'
                ).count()

                if today_posts < (site.posts_per_day or 1):
                    print(f"   >>> 🚀 GATILHO ATIVADO para {site.site_name}!")
                    execute_auto_post(site, app)
                else:
                    print(f"   [!] Ignorado: Limite de {site.posts_per_day} posts já atingido hoje.")

def execute_auto_post(site, app):
    """Gera o conteúdo e publica no WordPress."""
    try:
        # Aqui entrará sua função de IA no futuro
        print(f"   [*] Gerando post para {site.site_name}...")
        
        # Simulação de postagem (substitua pela lógica real de Requests)
        print(f"   [OK] Postagem simulada com sucesso para {site.site_name}")
        
    except Exception as e:
        print(f"   [ERRO] Falha ao processar {site.site_name}: {e}")