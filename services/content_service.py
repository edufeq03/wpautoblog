import requests
from requests.auth import HTTPBasicAuth
from models import db, ContentIdea, PostLog, Blog, CapturedContent
from services.ai_service import generate_text
from services.scraper_service import extrair_texto_da_url
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
model_name = os.environ.get("GROQ_MODEL_QUICK")

# Tentativa de importar serviços de imagem (proteção contra ausência do arquivo)
try:
    from services.image_service import processar_imagem_featured, upload_manual_image
except ImportError:
    processar_imagem_featured = None
    upload_manual_image = None

def get_groq_client():
    """Inicializa o cliente Groq usando a chave de API do ambiente."""
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- BUSCAS E RELATÓRIOS ---
def get_filtered_ideas(user_id, site_id=None):
    query = ContentIdea.query.join(Blog).filter(Blog.user_id == user_id, ContentIdea.is_posted == False)
    if site_id:
        query = query.filter(ContentIdea.blog_id == site_id)
    return query.order_by(ContentIdea.created_at.desc()).all()

def get_post_reports(user_id, site_id=None):
    query = PostLog.query.join(Blog).filter(Blog.user_id == user_id)
    if site_id:
        query = query.filter(PostLog.blog_id == site_id)
    return query.order_by(PostLog.posted_at.desc()).all()

# --- LÓGICA DE POSTAGEM MANUAL ---
def process_manual_post(user, site_id, title, content, action, image_file=None):
    """
    Processa o formulário de postagem manual.
    site_id vem do campo 'site_id' do formulário HTML.
    """
    if not site_id:
        return False, "Nenhum site selecionado."

    blog = Blog.query.filter_by(id=site_id, user_id=user.id).first_or_404()
    
    # 1. Upload de Imagem se fornecida
    wp_image_id = None
    if image_file and upload_manual_image:
        auth = HTTPBasicAuth(blog.wp_user, blog.wp_app_password)
        wp_image_id = upload_manual_image(image_file, blog.wp_url, auth)

    # Geração de imagem por IA (se NÃO houver imagem manual e o plano permitir)
    if not wp_image_id and user.plan_details and user.plan_details.has_images:
        auth = HTTPBasicAuth(blog.wp_user, blog.wp_app_password)
        wp_image_id = processar_imagem_featured(title, blog.wp_url, auth)

    # 2. Publicar Agora ou Agendar
    if action == 'now':
        response = _send_to_wp(blog, title, content, wp_image_id)
        if response and response.status_code in [200, 201]:
            data = response.json()
            log = PostLog(
                blog_id=blog.id, title=title, status="Publicado",
                wp_post_id=data.get('id'), post_url=data.get('link')
            )
            db.session.add(log)
            db.session.commit()
            return True, "Publicado com sucesso no WordPress!"
        return False, "Erro ao conectar com a API do WordPress."
    else:
        # Modo Fila (Agendamento)
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

# --- FLUXO DE PUBLICAÇÃO (FILA) ---
def publish_content_flow(idea, user):
    if getattr(user, 'is_demo', False):
        return True, "Modo Demo: Simulação concluída."

    # Se for manual usa o texto guardado, senão gera com IA
    texto = idea.full_content if getattr(idea, 'is_manual', False) else generate_text(f"Escreva sobre: {idea.title}")
    id_img = idea.featured_image_id if getattr(idea, 'is_manual', False) else None

    # Se não for manual e o plano permitir, gera imagem via IA
    if not id_img and not getattr(idea, 'is_manual', False):
        if user.plan_details and user.plan_details.has_images:
            auth = HTTPBasicAuth(idea.blog.wp_user, idea.blog.wp_app_password)
            id_img = processar_imagem_featured(idea.title, idea.blog.wp_url, auth)

    response = _send_to_wp(idea.blog, idea.title, texto, id_img)
    if response and response.status_code in [200, 201]:
        idea.is_posted = True
        db.session.commit()
        return True, "Publicado!"
    return False, "Erro na API do WordPress."

def _send_to_wp(blog, titulo, conteudo, id_img):
    """Envia os dados finais para o WP via REST API."""
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

# --- OUTRAS UTILIDADES ---
def generate_ideas_logic(blog):
    prompt = f"Gere 10 títulos de artigos sobre {blog.site_name}. Um por linha."
    resultado = generate_text(prompt)
    if resultado:
        titulos = [t.strip() for t in resultado.split('\n') if t.strip()]
        for t in titulos:
            db.session.add(ContentIdea(title=t.lstrip('0123456789. '), blog_id=blog.id))
        db.session.commit()
        return len(titulos)
    return 0

def process_spy_writer(url, is_demo):
    if is_demo: return "Conteúdo demonstrativo (Modo Demo)."
    raw = extrair_texto_da_url(url)
    return generate_text(f"Reescreva: {raw[:3000]}") if raw else None

# --- SPY WRITER LOGIC ---
def analyze_spy_link(url, is_demo):
    if is_demo:
        return {"title": "Título Exemplo", "text": "Conteúdo exemplo."}
    
    raw_text = extrair_texto_da_url(url)
    if not raw_text:
        return None
    
    # Prompt mais rígido: "Apenas o título", "Sem introdução"
    title_prompt = f"Gere apenas um título curto e chamativo (máximo 80 caracteres) para um post baseado neste texto. Não escreva 'Aqui está o título' nem numere opções: {raw_text[:500]}"
    content_prompt = f"Reescreva o conteúdo de forma original e profissional para blog: {raw_text[:3500]}"
    
    title = generate_text(title_prompt).strip().replace('"', '')
    
    # LIMITADOR DE DANOS: Se a IA falhar e mandar um texto enorme, cortamos em 150 caracteres
    if len(title) > 150:
        title = title[:147] + "..."

    return {
        "title": title,
        "text": generate_text(content_prompt)
    }

def sync_sources_logic(fontes, scraper_func):
    """Varre as fontes, extrai texto e gera insights com IA."""
    from models import db, CapturedContent # Import local para evitar erros de escopo
    groq_client = get_groq_client()
    contador = 0
    
    for fonte in fontes:
        texto_real = scraper_func(fonte.source_url)
        if texto_real:
            try:
                response = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "Você é um analista de tendências. Extraia os 3 pontos MAIS IMPORTANTES deste conteúdo para um novo artigo de blog. Seja conciso."},
                        {"role": "user", "content": texto_real[:4000]}
                    ]
                )
                
                # Criamos o registro do insight
                nova_captura = CapturedContent(
                    source_id=fonte.id, 
                    site_id=fonte.blog_id, 
                    url=fonte.source_url, 
                    title=f"Insight: {fonte.source_url.split('//')[-1][:30]}", 
                    content_summary=response.choices[0].message.content
                )
                db.session.add(nova_captura)
                contador += 1
            except Exception as e:
                print(f"Erro no Radar para {fonte.source_url}: {e}")
    
    db.session.commit()
    return contador

def convert_radar_insight_to_idea(insight_id):
    """Transforma um insight do Radar em uma ideia na fila de postagem."""
    insight = CapturedContent.query.get_or_404(insight_id)
    
    # Criamos uma nova ideia baseada no insight
    nova_ideia = ContentIdea(
        title=insight.title if insight.title != "Insight Automático" else f"Post sobre: {insight.url[:30]}",
        blog_id=insight.site_id,
        is_posted=False
    )
    
    db.session.add(nova_ideia)
    db.session.commit()
    return True