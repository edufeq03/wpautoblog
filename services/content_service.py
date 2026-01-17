import requests
from requests.auth import HTTPBasicAuth
from models import db, ContentIdea, PostLog, Blog, CapturedContent, ApiUsage
from services.ai_service import generate_text
from services.scraper_service import extrair_texto_da_url
import os
from datetime import datetime, date
from dotenv import load_dotenv
from groq import Groq
from bs4 import BeautifulSoup

load_dotenv()
model_name = os.environ.get("GROQ_MODEL_QUICK", "llama-3.3-70b-versatile")

# Proteção para serviços de imagem
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
    query = PostLog.query.join(Blog).filter(Blog.user_id == user_id)
    if site_id:
        query = query.filter(PostLog.blog_id == site_id)
    return query.order_by(PostLog.posted_at.desc()).all()

# --- FLUXO DO RADAR (INSIGHTS) ---
def sync_sources_logic(fontes, scraper_func):
    """Extrai conteúdo das fontes e gera insights analíticos."""
    groq_client = get_groq_client()
    contador = 0
    
    for fonte in fontes:
        texto_real = scraper_func(fonte.source_url)
        if texto_real:
            try:
                response = groq_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "Analise o texto e extraia os 3 pontos mais importantes para um post. Responda em texto simples."},
                        {"role": "user", "content": texto_real[:4000]}
                    ]
                )
                
                nova_captura = CapturedContent(
                    source_id=fonte.id, 
                    site_id=fonte.blog_id, 
                    url=fonte.source_url, 
                    title=f"Insight: {fonte.source_url.split('/')[-1][:30]}", 
                    content_summary=response.choices[0].message.content
                )
                db.session.add(nova_captura)
                contador += 1
            except Exception as e:
                print(f"Erro no Radar para {fonte.source_url}: {e}")
    
    db.session.commit()
    return contador

def convert_radar_insight_to_idea(insight_id):
    """Ponte: Transforma Insight em Título SEO + Contexto para a Fila."""
    insight = CapturedContent.query.get_or_404(insight_id)
    groq_client = get_groq_client()

    prompt = (
        f"Transforme este resumo em um título de post atraente e SEO: '{insight.content_summary}'. "
        "Retorne apenas o título, sem aspas."
    )

    try:
        res = groq_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8
        )
        titulo_gerado = res.choices[0].message.content.strip().replace('"', '')

        nova_ideia = ContentIdea(
            title=titulo_gerado,
            blog_id=insight.site_id,
            context_insight=insight.content_summary, # Salva o resumo para guiar o post final
            is_posted=False
        )
        db.session.add(nova_ideia)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Erro na conversão: {e}")
        return False

# --- PUBLICAÇÃO FINAL ---
def _gerar_texto_do_artigo(idea):
    """Subfunção 1: Cuida apenas da inteligência artificial."""
    if idea.context_insight:
        prompt = (
            f"Escreva um artigo de blog completo com o título '{idea.title}'. "
            f"Baseie o conteúdo nestes fatos: {idea.context_insight}"
        )
    else:
        prompt = f"Escreva um artigo de blog completo sobre: {idea.title}"
    
    return generate_text(prompt)

def _obter_imagem_destacada(idea):
    """Subfunção 2: Cuida apenas da lógica de imagem."""
    wp_image_id = idea.featured_image_id
    if not wp_image_id and processar_imagem_featured:
        auth = HTTPBasicAuth(idea.blog.wp_user, idea.blog.wp_app_password)
        wp_image_id = processar_imagem_featured(idea.title, idea.blog.wp_url, auth)
    return wp_image_id

def publish_content_flow(idea, user):
    """
    Agora atua como coordenador do fluxo.
    """
    if getattr(user, 'is_demo', False):
        return True, "Modo Demo ativo."

    # ETAPA 1: Gerar Texto
    conteudo_post = gerar_conteudo_ia(idea.title, idea.context_insight)
    if not conteudo_post:
        return False, "A IA falhou ao gerar o conteúdo. Tente novamente."

    # ETAPA 2: Preparar Imagem
    wp_image_id = preparar_imagem_post(idea)

    # ETAPA 3: Enviar ao WordPress
    try:
        response = _send_to_wp(idea.blog, idea.title, conteudo_post, wp_image_id)
        
        if response and response.status_code in [200, 201]:
            data = response.json()
            # Salvar Logs e Marcar como Postado
            registrar_sucesso_post(idea, user, conteudo_post, data)
            return True, "Post publicado com sucesso!"
        
        return False, f"WordPress rejeitou o post (Erro {response.status_code if response else 'Conexão'})."

    except Exception as e:
        print(f">>> [ERRO CRÍTICO] Falha na publicação: {e}")
        return False, "Erro inesperado ao conectar com o WordPress."

def registrar_sucesso_post(idea, user, conteudo, wp_data):
    """Salva os dados no banco após confirmação de sucesso."""
    idea.is_posted = True
    log = PostLog(
        blog_id=idea.blog_id,
        title=idea.title,
        content=conteudo[:500],
        status="Publicado",
        wp_post_id=wp_data.get('id'),
        post_url=wp_data.get('link')
    )
    db.session.add(log)
    user.last_post_date = date.today()
    db.session.commit()
         


    
def process_manual_post(user, site_id, title, content, action, image_file=None):
    blog = Blog.query.filter_by(id=site_id, user_id=user.id).first()
    if not blog:
        return False, "Site não encontrado."

    wp_image_id = None
    if image_file and image_file.filename != '':
        if upload_manual_image:
            # IMPORTANTE: upload_manual_image deve retornar o ID (int) da imagem no WP
            wp_image_id = upload_manual_image(image_file, blog.wp_url, (blog.wp_user, blog.wp_app_password))
            print(f">>> [DEBUG] Imagem enviada ao WP. ID recebido: {wp_image_id}")
    
    # Define o status baseado na escolha do usuário
    # Se for 'now' -> 'publish'. Se for qualquer outra coisa (como 'draft') -> 'draft'
    wp_status = 'publish' if action == 'now' else 'draft'
    
    response = _send_to_wp(blog, title, content, wp_image_id, status=wp_status)
    
    if response and response.status_code in [200, 201]:
        data = response.json()
        status_label = "Publicado" if wp_status == 'publish' else "Rascunho Enviado"
        
        log = PostLog(
            blog_id=blog.id,
            title=title,
            content=content[:500],
            status=status_label,
            wp_post_id=data.get('id'),
            post_url=data.get('link')
        )
        db.session.add(log)
        user.last_post_date = date.today()
        db.session.commit()
        return True, f"Sucesso! O post foi enviado como {status_label}."
    
    return False, "Erro ao comunicar com o WordPress."



# --- 1. SUBFUNÇÕES DE APOIO (ATOMICIDADE) ---

def gerar_conteudo_ia(titulo, contexto=None):
    """Responsabilidade: Apenas conversar com a IA e retornar o texto."""
    if contexto:
        prompt = (
            f"Escreva um artigo de blog completo com o título '{titulo}'. "
            f"Baseie o conteúdo nestes fatos: {contexto}"
        )
    else:
        prompt = f"Escreva um artigo de blog completo sobre: {titulo}"

    try:
        # Chama a sua função de serviço de IA existente
        conteudo = generate_text(prompt)
        return conteudo
    except Exception as e:
        print(f">>> [ERRO IA] Falha ao gerar texto: {e}")
        return None

def preparar_imagem_post(idea):
    """Responsabilidade: Resolver o ID da imagem destacada."""
    wp_image_id = idea.featured_image_id
    if not wp_image_id and processar_imagem_featured:
        try:
            auth = HTTPBasicAuth(idea.blog.wp_user, idea.blog.wp_app_password)
            wp_image_id = processar_imagem_featured(idea.title, idea.blog.wp_url, auth)
        except Exception as e:
            print(f">>> [AVISO IMAGEM] Falha ao processar imagem: {e}")
    return wp_image_id

def registrar_sucesso_post(idea, user, conteudo, wp_data):
    """Responsabilidade: Persistir os dados de sucesso no Banco de Dados."""
    idea.is_posted = True
    log = PostLog(
        blog_id=idea.blog_id,
        title=idea.title,
        content=conteudo[:500],
        status="Publicado",
        wp_post_id=wp_data.get('id'),
        post_url=wp_data.get('link')
    )
    db.session.add(log)
    user.last_post_date = date.today()
    db.session.commit()

# --- 2. FLUXO PRINCIPAL (COORDENADOR) ---

def publish_content_flow(idea, user_id):
    """Coordenador do fluxo: IA -> Imagem -> WordPress."""
    if getattr(user_id, 'is_demo', False):
        return True, "Modo Demo ativo."

    # PASSO 1: Geração de Texto
    conteudo_post = gerar_conteudo_ia(idea.title, idea.context_insight)
    if not conteudo_post:
        return False, "Erro: A IA não conseguiu gerar o texto."

    # PASSO 2: Imagem Destacada
    wp_image_id = preparar_imagem_post(idea)

    # PASSO 3: Envio ao WordPress
    try:
        response = _send_to_wp(idea.blog, idea.title, conteudo_post, wp_image_id)
        
        if response and response.status_code in [200, 201]:
            data = response.json()
            registrar_sucesso_post(idea, user_id, conteudo_post, data)
            return True, "Post publicado com sucesso!"
        
        return False, f"O WordPress recusou a postagem (Status: {response.status_code if response else 'Timeout'})"

    except Exception as e:
        print(f">>> [ERRO CRÍTICO WP] {e}")
        return False, "Erro de conexão com o seu site WordPress."
    
# --- 3. OUTRAS FUNÇÕES DE LÓGICA ---

def generate_ideas_logic(blog):
    """Gera 5 ideias de títulos SEO."""
    groq_client = get_groq_client()
    prompt_sistema = "Você é um estrategista de conteúdo SEO. Retorne APENAS os títulos, um por linha."
    prompt_usuario = f"Gere 5 títulos de posts para o blog: {blog.site_name}"

    try:
        response = groq_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.7
        )
        conteudo = response.choices[0].message.content.strip()
        linhas = [l.strip() for l in conteudo.split('\n') if len(l.strip()) > 5]
        
        count = 0
        for titulo in linhas:
            titulo_limpo = titulo.lstrip('0123456789. -')
            db.session.add(ContentIdea(blog_id=blog.id, title=titulo_limpo))
            count += 1
        db.session.commit()
        return count
    except Exception as e:
        print(f"Erro ao gerar ideias: {e}")
        return 0

import requests
from bs4 import BeautifulSoup

def analyze_spy_link(url, is_demo=False):
    """
    Analisa uma URL externa e retorna título e conteúdo extraído.
    """
    # 1. Inicializa a variável para evitar erro de referência local
    soup = None 
    
    try:
        # Define um User-Agent para evitar ser bloqueado por sites
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Lança erro para status 4xx ou 5xx
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
    except Exception as e:
        print(f"Erro ao acessar a URL {url}: {e}")
        return None

    # 2. Verifica se o soup foi criado com sucesso antes de prosseguir
    if not soup:
        return None

    try:
        # 3. Extração segura de dados
        # Tenta pegar o H1, se não houver, tenta o title da página
        title_tag = soup.find('h1')
        title = title_tag.get_text().strip() if title_tag else soup.title.string if soup.title else "Sem Título"

        # Tenta extrair o corpo do texto (parágrafos)
        paragraphs = soup.find_all('p')
        content = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text()) > 20])

        if not content:
            return None

        # 4. Aqui você chamaria sua IA (Groq) para reescrever o texto extraído
        # rephrased_content = call_groq_to_rewrite(title, content)
        
        return {
            "title": title,
            "content": content # ou rephrased_content após integrar a IA
        }

    except Exception as e:
        print(f"Erro ao processar conteúdo do HTML: {e}")
        return None

def _send_to_wp(blog, titulo, conteudo, id_img, status=None):
    post_status = status if status else (blog.post_status or 'publish')
    payload = {'title': titulo, 'content': conteudo, 'status': post_status}
    if id_img: payload['featured_media'] = int(id_img)

    auth = HTTPBasicAuth(blog.wp_user, blog.wp_app_password)
    try:
        url = f"{blog.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        return requests.post(url, auth=auth, json=payload, timeout=30)
    except Exception as e:
        print(f"Erro na requisição WP: {e}")
        return None