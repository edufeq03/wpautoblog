import os
from groq import Groq
from dotenv import load_dotenv
from models import CapturedContent, ContentSource, db
from utils.scrapers import extrair_texto_da_url

load_dotenv()
def get_groq_client():
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

def preparar_contexto_brainstorm(site):
    """Lê a memória do Radar para injetar no Gerador de Ideias."""
    contexto = f"Temas principais do blog: {site.macro_themes}\n"
    
    # Busca capturas vinculadas ao site através da fonte
    conteudos_recentes = CapturedContent.query.join(ContentSource).filter(
        ContentSource.blog_id == site.id
    ).order_by(CapturedContent.created_at.desc()).limit(5).all()
    
    if conteudos_recentes:
        contexto += "\nTendências recentes detectadas no Radar para inspiração:\n"
        for item in conteudos_recentes:
            # Tenta pegar o título ou usa um fallback
            titulo = item.title if item.title else "Conteúdo Recente"
            contexto += f"- {titulo}: {item.summary[:200]}...\n"
            
    return contexto

def processar_radar_automatico():
    """Motor de captura automática acionado pelo Scheduler."""
    # Buscamos todas as fontes cadastradas
    fontes = ContentSource.query.all()
    
    for fonte in fontes:
        try:
            print(f"Lendo fonte: {fonte.source_url}")
            conteudo_bruto = extrair_texto_da_url(fonte.source_url)
            
            if conteudo_bruto:
                # IA processa o resumo
                groq_client = get_groq_client()
                completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "Você é um analista de conteúdo. Resuma o texto em 3 tópicos curtos e identifique se é Educativo, Notícia ou Venda."},
                        {"role": "user", "content": conteudo_bruto[:4000]}
                    ]
                )
                
                resumo = completion.choices[0].message.content
                
                # Salva na memória (CapturedContent)
                nova_captura = CapturedContent(
                    source_id=fonte.id,
                    site_id=fonte.blog_id, # Importante para o vínculo com o site
                    url=fonte.source_url,
                    title=f"Captura Automática: {fonte.source_url.split('/')[-1]}",
                    summary=resumo,
                    analysis="Processado via Scheduler"
                )
                db.session.add(nova_captura)
                print(f"Sucesso ao processar: {fonte.source_url}")
            
            # Commit por fonte para evitar perda de progresso se uma falhar
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao processar {fonte.source_url}: {e}")