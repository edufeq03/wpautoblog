import os
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

def generate_text(prompt, system_prompt="Você é um assistente especialista em SEO.", quick=False):
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