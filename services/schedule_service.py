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
    """Calcula os momentos de postagem baseados no horário inicial e na frequência."""
    horarios = []
    try:
        base_dt = datetime.strptime(horario_base, '%H:%M')
        intervalo_horas = 24 / posts_per_day
        for i in range(posts_per_day):
            momento = base_dt + timedelta(hours=i * intervalo_horas)
            horarios.append(momento.strftime('%H:%M'))
    except Exception as e:
        print(f"Erro ao calcular horários: {e}")
        horarios = [horario_base]
    return horarios

def check_and_post_all_sites(app):
    """Varre o banco e dispara postagens nos horários distribuídos."""
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
            lista_horarios = calcular_horarios_do_dia(site.schedule_time, site.posts_per_day or 1)
            
            print(f"| Site: {site.site_name[:15].ljust(15)} | Agora: {current_time_str} | Alvos: {lista_horarios} |")

            if current_time_str in lista_horarios:
                # CORREÇÃO PARA POSTGRESQL (to_char em vez de strftime)
                ja_postou_agora = PostLog.query.filter(
                    PostLog.blog_id == site.id,
                    db.func.date(PostLog.posted_at) == now_in_tz.date(),
                    db.func.to_char(PostLog.posted_at, 'HH24:MI') == current_time_str
                ).first()

                if not ja_postou_agora:
                    print(f"   >>> 🚀 GATILHO ATIVADO para {site.site_name}")
                    execute_auto_post(site, app)
                else:
                    print(f"   [!] Aguardando: Post deste horário já concluído.")

def execute_auto_post(site, app):
    """Lógica principal: IA -> Imagem (com Fallback) -> WordPress"""
    try:
        # --- ETAPA 1: GERAÇÃO DE TEXTO ---
        print(f"   🧠 [IA] Gerando conteúdo...")
        prompt_sistema = site.master_prompt or "Você é um redator especialista em SEO."
        temas = site.macro_themes or "Tecnologia"

        prompt_titulo = f"Crie um título viral sobre: {temas}. Apenas o título."
        titulo_final = generate_text(prompt_titulo, system_prompt=prompt_sistema, quick=True)

        prompt_corpo = f"Escreva um artigo detalhado em HTML sobre {temas}."
        conteudo_final = generate_text(prompt_corpo, system_prompt=prompt_sistema)

        if not titulo_final or not conteudo_final:
            return

        # --- ETAPA 2: GERAÇÃO DE IMAGEM (COM TRATAMENTO DE ERRO DE SALDO) ---
        auth_wp = HTTPBasicAuth(site.wp_user, site.wp_app_password)
        id_imagem_destacada = None
        
        try:
            print(f"   🎨 [IMAGEM] Tentando gerar imagem...")
            id_imagem_destacada = processar_imagem_featured(titulo_final, site.wp_url, auth_wp)
        except Exception as img_err:
            # Se cair aqui (billing_hard_limit_reached ou qualquer outro erro da OpenAI)
            print(f"   ⚠️ Falha na API de Imagem: {img_err}")
            print(f"   👉 O post será publicado APENAS COM TEXTO para não quebrar o fluxo.")
            id_imagem_destacada = None 

        # --- ETAPA 3: PUBLICAÇÃO ---
        print(f"   📤 [WP] Publicando no site...")
        wp_endpoint = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        
        payload = {
            "title": titulo_final,
            "content": conteudo_final,
            "status": site.post_status or "publish",
        }
        
        # Só adiciona a mídia se o ID existir
        if id_imagem_destacada:
            payload["featured_media"] = id_imagem_destacada

        response = requests.post(wp_endpoint, json=payload, auth=auth_wp, timeout=60)

        if response.status_code == 201:
            link_final = response.json().get('link')
            print(f"   ✅ [SUCESSO] Post publicado: {link_final}")
            
            new_log = PostLog(blog_id=site.id, title=titulo_final, status='Publicado', post_url=link_final)
            db.session.add(new_log)
            db.session.commit()
        else:
            print(f"   ❌ Erro WP ({response.status_code}): {response.text}")

    except Exception as e:
        print(f"   💥 Erro Crítico: {str(e)}")