import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from flask_login import current_user

load_dotenv()

def generate_text(prompt, system_prompt="Você é um assistente especialista em SEO.", quick=False):
    # TRAVA DE SEGURANÇA PARA CONTA DEMO
    if hasattr(current_user, 'email') and current_user.email == "demo@wpautoblog.com":
        return "Este é um exemplo de texto gerado automaticamente pela IA para o usuário de demonstração. Em uma conta real, este conteúdo seria personalizado de acordo com o seu tema e SEO."
    
    model_name = os.environ.get("GROQ_MODEL_QUICK") if quick else os.environ.get("GROQ_MODEL_MAIN")
    
    # O LangChain gerencia o cliente internamente de forma mais isolada
    llm = ChatGroq(
        temperature=0.7,
        model_name=model_name,
        groq_api_key=os.environ.get("GROQ_API_KEY")
    )
    
    try:
        response = llm.invoke([
            ("system", system_prompt),
            ("user", prompt)
        ])
        return response.content
    except Exception as e:
        print(f"❌ Erro LangChain/Groq: {e}")
        return None

def criar_prompt_visual(titulo_post):
    prompt = f"Descreva uma cena fotográfica realista para o post: {titulo_post}. Sem textos."
    return generate_text(prompt, system_prompt="Você é um diretor de arte.", quick=True)