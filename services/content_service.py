import requests
from requests.auth import HTTPBasicAuth
from models import db, ContentIdea, PostLog, Blog
from services.ai_service import generate_text
from services.image_service import processar_imagem_featured # Importação limpa

def get_filtered_ideas(user_id, site_id=None):
    """Busca ideias não postadas de um usuário, com filtro opcional por site."""
    query = ContentIdea.query.join(Blog).filter(Blog.user_id == user_id, ContentIdea.is_posted == False)
    if site_id:
        query = query.filter(ContentIdea.blog_id == site_id)
    return query.order_by(ContentIdea.created_at.desc()).all()

def get_post_reports(user_id, site_id=None):
    """Busca o histórico de postagens do usuário."""
    query = PostLog.query.join(Blog).filter(Blog.user_id == user_id)
    if site_id:
        query = query.filter(PostLog.blog_id == site_id)
    return query.order_by(PostLog.posted_at.desc()).all()

def generate_ideas_logic(blog):
    """Lógica para criar 10 novas ideias via IA."""
    prompt = f"Gere 10 títulos de artigos para um blog sobre {blog.site_name}. Retorne um por linha, sem markdown."
    resultado = generate_text(prompt)
    if resultado:
        titulos = [t.strip() for t in resultado.split('\n') if t.strip()]
        for titulo in titulos:
            nova_ideia = ContentIdea(title=titulo.lstrip('0123456789. '), blog_id=blog.id)
            db.session.add(nova_ideia)
        db.session.commit()
        return len(titulos)
    return 0

def publish_content_flow(idea, user):
    """Fluxo completo: IA -> Imagem -> WordPress."""
    if getattr(user, 'is_demo', False): # Ponto 4: Checagem via atributo do banco
        return True, "Simulação concluída com sucesso (Modo Demo)."

    if user.credits <= 0:
        return False, "Saldo de créditos insuficiente."

    try:
        texto = generate_text(f"Escreva um artigo detalhado sobre: {idea.title}")
        
        id_img = None
        if user.plan_details and user.plan_details.has_images:
            auth = HTTPBasicAuth(idea.blog.wp_user, idea.blog.wp_app_password)
            id_img = processar_imagem_featured(idea.title, idea.blog.wp_url, auth)

        response = _send_to_wp(idea.blog, idea.title, texto, id_img)

        if response and response.status_code in [200, 201]:
            user.credits -= 1
            idea.is_posted = True
            data = response.json()
            log = PostLog(blog_id=idea.blog.id, title=idea.title, status="Publicado", 
                          wp_post_id=data.get('id'), post_url=data.get('link'))
            db.session.add(log)
            db.session.commit()
            return True, f"Publicado! Crédito debitado (Saldo: {user.credits})"
        
        return False, "Erro na API do WordPress."
    except Exception as e:
        db.session.rollback()
        return False, f"Falha: {str(e)}"

def _send_to_wp(blog, titulo, conteudo, id_img):
    """Comunicação técnica com WordPress."""
    payload = {'title': titulo, 'content': conteudo, 'status': blog.post_status or 'publish'}
    if id_img: payload['featured_media'] = id_img
    return requests.post(f"{blog.wp_url.rstrip('/')}/wp-json/wp/v2/posts",
                         auth=HTTPBasicAuth(blog.wp_user, blog.wp_app_password),
                         json=payload, timeout=30)