import requests
from requests.auth import HTTPBasicAuth
from models import db, ContentIdea, PostLog, Blog, CapturedContent, ApiUsage
from services.ai_service import generate_text
from services.scraper_service import extrair_texto_da_url
import os
from datetime import datetime, date
from dotenv import load_dotenv
from groq import Groq

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

# --- GERAÇÃO DE IDEIAS (BRAINSTORM) ---
def generate_ideas_logic(blog):
    """Gera 5 ideias de títulos SEO baseados no nome/nicho do blog."""
    groq_client = get_groq_client()
    
    prompt_sistema = (
        "Você é um estrategista de conteúdo SEO. Retorne APENAS os títulos, "
        "um por linha, sem números, sem aspas e sem markdown. Gere 5 títulos."
    )
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
        # --- LÓGICA DE VIGILÂNCIA ---
        # Pegamos o consumo real retornado pela API
        tokens = response.usage.total_tokens if hasattr(response, 'usage') else 0
        usage_log = ApiUsage(
            user_id=blog.user_id,
            api_name="Groq",
            feature="Generate Ideas",
            tokens_used=tokens
        )
        db.session.add(usage_log)
        # ----------------------------
        
        conteudo = response.choices[0].message.content.strip()
        linhas = [l.strip() for l in conteudo.split('\n') if len(l.strip()) > 5]
        
        count = 0
        for titulo in linhas:
            titulo_limpo = titulo.lstrip('0123456789. -')
            nova_ideia = ContentIdea(blog_id=blog.id, title=titulo_limpo, is_posted=False)
            db.session.add(nova_ideia)
            count += 1
        
        db.session.commit()
        return count
    except Exception as e:
        print(f"Erro ao gerar ideias: {e}")
        return 0

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
    """Função Principal: Agora ela apenas COORDENA as subfunções."""
    if getattr(user, 'is_demo', False):
        return True, "Modo Demo ativo."

    try:
        # 1. Geração do conteúdo
        conteudo_post = _gerar_texto_do_artigo(idea)
        if not conteudo_post:
            return False, "Erro ao gerar texto com a IA."

        # 2. Obtenção da imagem
        wp_image_id = _obter_imagem_destacada(idea)

        # 3. Envio ao WordPress (Comunicação Externa)
        response = _send_to_wp(idea.blog, idea.title, conteudo_post, wp_image_id)
        
        if response and response.status_code in [200, 201]:
            data = response.json()
            # Marcar como postado para não repetir
            idea.is_posted = True
            
            # 4. Registro de Logs (Banco de Dados)
            log = PostLog(
                blog_id=idea.blog_id,
                title=idea.title,
                content=conteudo_post[:500],
                status="Publicado",
                wp_post_id=data.get('id'),
                post_url=data.get('link')
            )
            db.session.add(log)
            user.last_post_date = date.today()
            db.session.commit()
            return True, "Post publicado com sucesso!"
        
        return False, "O WordPress recusou a publicação (verifique credenciais)."

    except Exception as e:
        db.session.rollback()
        print(f"Erro crítico no fluxo: {e}")
        return False, f"Erro interno: {str(e)}"

def _send_to_wp(blog, titulo, conteudo, id_img, status=None):
    # Se não for passado status, ele usa o padrão do banco (que geralmente é 'publish')
    post_status = status if status else (blog.post_status or 'publish')
    
    payload = {
        'title': titulo, 
        'content': conteudo, 
        'status': post_status  # Agora o WP respeitará 'draft' ou 'publish'
    }
    
    if id_img:
        payload['featured_media'] = int(id_img)

    auth = HTTPBasicAuth(blog.wp_user, blog.wp_app_password)
    try:
        url = f"{blog.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        r = requests.post(url, auth=auth, json=payload, timeout=30)
        return r
    except Exception as e:
        print(f"Erro na requisição WP: {e}")
        return None
    
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

def analyze_spy_link(url, is_demo=False):
    """
    Extrai o conteúdo de uma URL e usa IA para criar uma nova versão.
    """
    if not url:
        return None

    # 1. Extrai o texto bruto da URL informada
    # Certifique-se que o scraper_service está funcionando
    texto_extraido = extrair_texto_da_url(url)
    print(f"O texto extraido foi:\n{texto_extraido[:500]}...")
    
    if not texto_extraido:
        print(f"!!! [SPY-WRITER] Falha ao extrair texto da URL: {url}")
        return None

    # 2. Se for usuário demo, retorna um texto fixo para economizar tokens
    if is_demo:
        return {
            'title': "Título Exemplo do Spy Writer (Modo Demo)",
            'content': "Este é um conteúdo de exemplo gerado pelo modo espião. Na versão completa, a IA leria o site original e reescreveria o texto com SEO."
        }

    # 3. Usa a IA para processar o conteúdo
    try:
        prompt_sistema = "Você é um redator especialista em SEO e reescrita de artigos."
        prompt_usuario = f"""
        Analise o texto abaixo extraído de um site concorrente e crie um NOVO artigo baseado nele.
        O novo artigo deve ter um título chamativo e um conteúdo rico em detalhes, formatado em HTML (apenas tags p, h2, h3, ul, li).
        Não copie o texto original, crie uma versão única e melhorada.
        
        Texto original:
        {texto_extraido[:4000]} 
        
        Responda EXATAMENTE neste formato:
        TITULO: [O seu título aqui]
        CONTEUDO: [O seu conteúdo em HTML aqui]
        """
        
        resposta_ia = generate_text(prompt_usuario, system_prompt=prompt_sistema)
        
        if resposta_ia and "TITULO:" in resposta_ia and "CONTEUDO:" in resposta_ia:
            partes = resposta_ia.split("CONTEUDO:")
            titulo = partes[0].replace("TITULO:", "").strip()
            conteudo = partes[1].strip()
            
            return {
                'title': titulo,
                'content': resposta_ia if resposta_ia else texto_extraido
            }
            
    except Exception as e:
        print(f"!!! [SPY-WRITER] Erro ao processar IA: {e}")
        
    return None