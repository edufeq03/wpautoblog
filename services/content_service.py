import requests
from requests.auth import HTTPBasicAuth
from models import db, ContentIdea, PostLog, Blog, CapturedContent
from services.ai_service import generate_text
from services.scraper_service import extrair_texto_da_url
import os
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
model_name = os.environ.get("GROQ_MODEL_QUICK")

try:
    from services.image_service import processar_imagem_featured, upload_manual_image
except ImportError:
    processar_imagem_featured = None
    upload_manual_image = None

def get_groq_client():
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- BUSCAS E RELATÓRIOS ---
def get_filtered_ideas(user_id, site_id=None):
    query = ContentIdea.query.join(Blog).filter(Blog.user_id == user_id, ContentIdea.is_posted == False)
    if site_id:
        query = query.filter(ContentIdea.blog_id == site_id)
    return query.order_by(ContentIdea.created_at.desc()).all()

def get_post_reports(user_id, site_id=None):
    # Esta função alimenta o seu Post Report
    query = PostLog.query.join(Blog).filter(Blog.user_id == user_id)
    if site_id:
        query = query.filter(PostLog.blog_id == site_id)
    return query.order_by(PostLog.posted_at.desc()).all()

# --- LÓGICA DE POSTAGEM MANUAL ---
def process_manual_post(user, site_id, title, content, action, image_file=None):
    if not site_id:
        return False, "Nenhum site selecionado."

    blog = Blog.query.filter_by(id=site_id, user_id=user.id).first_or_404()
    
    wp_image_id = None
    if image_file and upload_manual_image:
        auth = HTTPBasicAuth(blog.wp_user, blog.wp_app_password)
        wp_image_id = upload_manual_image(image_file, blog.wp_url, auth)

    if not wp_image_id and user.plan_details and user.plan_details.has_images:
        auth = HTTPBasicAuth(blog.wp_user, blog.wp_app_password)
        wp_image_id = processar_imagem_featured(title, blog.wp_url, auth)

    if action == 'now':
        response = _send_to_wp(blog, title, content, wp_image_id)
        if response and response.status_code in [200, 201]:
            data = response.json()
            # SALVAMENTO NO LOG (Post Report)
            log = PostLog(
                blog_id=blog.id, 
                title=title, 
                content=content[:500],
                status="Publicado",
                wp_post_id=data.get('id'), 
                post_url=data.get('link')
            )
            db.session.add(log)
            db.session.commit()
            return True, "Publicado com sucesso no WordPress!"
        return False, "Erro ao conectar com a API do WordPress."
    else:
        nova_ideia = ContentIdea(
            title=title,
            blog_id=blog.id,
            full_content=content,
            featured_image_id=wp_image_id,
            is_manual=True,
            is_posted=False
        )
        db.session.add(nova_ideia)
        db.session.commit()
        return True, "Post manual salvo na fila de postagem!"

# --- FLUXO DE PUBLICAÇÃO (AUTOMÁTICO / FILA) ---
def publish_content_flow(idea, user):
    """Executa a postagem de uma ideia da fila e gera o LOG."""
    if getattr(user, 'is_demo', False):
        return True, "Modo Demo: Simulação concluída."

    texto = idea.full_content if getattr(idea, 'is_manual', False) else generate_text(f"Escreva um artigo de blog sobre: {idea.title}")
    id_img = idea.featured_image_id if getattr(idea, 'is_manual', False) else None

    if not id_img and not getattr(idea, 'is_manual', False):
        if user.plan_details and user.plan_details.has_images:
            auth = HTTPBasicAuth(idea.blog.wp_user, idea.blog.wp_app_password)
            id_img = processar_imagem_featured(idea.title, idea.blog.wp_url, auth)

    response = _send_to_wp(idea.blog, idea.title, texto, id_img)
    
    if response and response.status_code in [200, 201]:
        data = response.json()
        
        # 1. Marcar ideia como postada
        idea.is_posted = True
        
        # 2. CRIAR LOG PARA O POST REPORT (Isso faltava no fluxo automático)
        novo_log = PostLog(
            blog_id=idea.blog_id,
            title=idea.title,
            content=texto[:500],
            status="Publicado",
            wp_post_id=data.get('id'),
            post_url=data.get('link')
        )
        db.session.add(novo_log)
        db.session.commit()
        return True, "Publicado!"
    
    return False, "Erro na API do WordPress."

def _send_to_wp(blog, titulo, conteudo, id_img):
    payload = {'title': titulo, 'content': conteudo, 'status': blog.post_status or 'publish'}
    if id_img: payload['featured_media'] = id_img
    
    try:
        return requests.post(
            f"{blog.wp_url.rstrip('/')}/wp-json/wp/v2/posts",
            auth=HTTPBasicAuth(blog.wp_user, blog.wp_app_password),
            json=payload, timeout=30
        )
    except:
        return None

# --- RADAR LOGIC ---
def sync_sources_logic(fontes, scraper_func):
    """Varre as fontes e gera insights usando os nomes de campos do models.py."""
    from models import db, CapturedContent
    groq_client = get_groq_client()
    contador = 0
    
    for fonte in fontes:
        texto_real = scraper_func(fonte.source_url)
        if texto_real:
            try:
                response = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "Você é um analista. Extraia 3 insights para posts baseados neste texto. Responda apenas o texto simples."},
                        {"role": "user", "content": texto_real[:4000]}
                    ]
                )
                
                # Ajustado para os nomes do seu models.py: content_summary e original_url
                nova_captura = CapturedContent(
                    source_id=fonte.id, 
                    site_id=fonte.blog_id, 
                    original_url=fonte.source_url, 
                    title=f"Insight: {fonte.source_url.split('/')[-1][:30]}", 
                    content_summary=response.choices[0].message.content
                )
                db.session.add(nova_captura)
                contador += 1
            except Exception as e:
                print(f"Erro no Radar: {e}")
    
    db.session.commit()
    return contador

def convert_radar_insight_to_idea(insight_id):
    insight = CapturedContent.query.get_or_404(insight_id)
    nova_ideia = ContentIdea(
        title=insight.title,
        blog_id=insight.site_id,
        is_posted=False
    )
    db.session.add(nova_ideia)
    db.session.commit()
    return True