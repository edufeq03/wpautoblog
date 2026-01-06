import os
import requests
import pytz
from datetime import datetime, timedelta
from requests.auth import HTTPBasicAuth
from models import db, Blog, PostLog

# Importação dos seus serviços de IA e Imagem
from services.ai_service import generate_text
from services.image_service import processar_imagem_featured

def calcular_horarios_do_dia(horario_base, posts_per_day):
    """
    Calcula os momentos de postagem baseados no horário inicial e na frequência.
    Ex: 08:00 com 4 posts/dia -> ['08:00', '14:00', '20:00', '02:00']
    """
    horarios = []
    try:
        # Converte a string 'HH:MM' em objeto datetime para cálculo
        base_dt = datetime.strptime(horario_base, '%H:%M')
        # Divide as 24h do dia pelo número de posts
        intervalo_horas = 24 / posts_per_day
        
        for i in range(posts_per_day):
            momento = base_dt + timedelta(hours=i * intervalo_horas)
            horarios.append(momento.strftime('%H:%M'))
    except Exception as e:
        print(f"Erro ao calcular horários: {e}")
        horarios = [horario_base] # Fallback para o horário original
        
    return horarios

def check_and_post_all_sites(app):
    """Varre o banco e dispara postagens nos horários distribuídos."""
    with app.app_context():
        sites = Blog.query.all()
        
        print(f"\n--- [VARREDURA {datetime.now().strftime('%H:%M:%S')}] ---")

        for site in sites:
            # 1. Configuração de Fuso Horário
            tz_name = site.timezone or 'America/Sao_Paulo'
            try:
                tz = pytz.timezone(tz_name)
            except:
                tz = pytz.timezone('America/Sao_Paulo')
            
            now_in_tz = datetime.now(tz)
            current_time_str = now_in_tz.strftime('%H:%M')
            
            # 2. Cálculo de janelas de postagem
            # Se posts_per_day for 1, ele retorna apenas o schedule_time original
            lista_horarios = calcular_horarios_do_dia(site.schedule_time, site.posts_per_day or 1)
            
            print(f"| Site: {site.site_name[:15].ljust(15)} | Agora: {current_time_str} | Alvos: {lista_horarios} |")

            # 3. Verificação de Gatilho
            if current_time_str in lista_horarios:
                
                # Checa se já houve postagem NESTE MINUTO específico hoje
                # Isso evita que o scheduler dispare 2x no mesmo minuto
                ja_postou_agora = PostLog.query.filter(
                    PostLog.blog_id == site.id,
                    db.func.date(PostLog.posted_at) == now_in_tz.date(),
                    db.func.to_char(PostLog.posted_at, 'HH24:MI') == current_time_str
                ).first()

                if not ja_postou_agora:
                    print(f"   >>> 🚀 GATILHO ATIVADO: Iniciando ciclo para {site.site_name}")
                    execute_auto_post(site, app)
                else:
                    print(f"   [!] Aguardando: Post deste horário ({current_time_str}) já concluído.")

def execute_auto_post(site, app):
    """Lógica principal: IA -> Imagem -> WordPress"""
    try:
        # --- ETAPA 1: GERAÇÃO DE TEXTO (GROQ) ---
        print(f"   🧠 [IA] Gerando título e artigo...")
        
        prompt_sistema = site.master_prompt or "Você é um redator especialista em SEO."
        temas = site.macro_themes or "Tecnologia e Inovação"

        prompt_titulo = f"Crie um título viral e chamativo sobre: {temas}. Apenas o título."
        titulo_final = generate_text(prompt_titulo, system_prompt=prompt_sistema, quick=True)

        prompt_corpo = f"Escreva um artigo de blog detalhado sobre {temas}. Use tags HTML <h2>, <h3> e <p>. Mínimo 500 palavras."
        conteudo_final = generate_text(prompt_corpo, system_prompt=prompt_sistema)

        if not titulo_final or not conteudo_final:
            raise Exception("Falha na geração de conteúdo via Groq.")

        # --- ETAPA 2: GERAÇÃO DE IMAGEM (DALL-E 3) ---
        print(f"   🎨 [IMAGEM] Gerando e enviando mídia...")
        auth_wp = HTTPBasicAuth(site.wp_user, site.wp_app_password)
        
        id_imagem_destacada = None
        try:
            # Sua função no image_service já faz o upload e retorna o ID
            id_imagem_destacada = processar_imagem_featured(titulo_final, site.wp_url, auth_wp)
        except Exception as img_err:
            print(f"   ⚠️ Erro na imagem (prosseguindo sem): {img_err}")

        # --- ETAPA 3: PUBLICAÇÃO (WORDPRESS API) ---
        print(f"   📤 [WP] Publicando no site...")
        wp_endpoint = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        
        payload = {
            "title": titulo_final,
            "content": conteudo_final,
            "status": site.post_status or "publish",
            "featured_media": id_imagem_destacada
        }

        response = requests.post(wp_endpoint, json=payload, auth=auth_wp, timeout=60)

        if response.status_code == 201:
            link_final = response.json().get('link')
            print(f"   ✅ [SUCESSO] Post publicado: {link_final}")
            
            # --- ETAPA 4: LOG NO BANCO ---
            new_log = PostLog(
                blog_id=site.id,
                title=titulo_final,
                status='Publicado',
                post_url=link_final
            )
            db.session.add(new_log)
            db.session.commit()
        else:
            print(f"   ❌ Erro WP ({response.status_code}): {response.text}")

    except Exception as e:
        print(f"   💥 Erro Crítico: {str(e)}")