import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Centralização de Modelos
class AIConfig:
    # Modelos de Texto (Groq)
    TEXT_MODEL_MAIN = os.environ.get("GROQ_MODEL_MAIN", "llama-3.3-70b-versatile")
    TEXT_MODEL_QUICK = os.environ.get("GROQ_MODEL_QUICK", "llama-3.1-8b-instant")
    
    # Modelo de Imagem (Ex: DALL-E, Stability, Leonardo)
    IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "dall-e-3")

# Cliente Groq
def get_groq_client():
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Função Única para Texto
def generate_text(prompt, system_prompt="Você é um assistente prestativo.", quick=False):
    client = get_groq_client()
    model = AIConfig.TEXT_MODEL_QUICK if quick else AIConfig.TEXT_MODEL_MAIN
    
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model=model,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Erro na IA (Texto): {e}")
        return None

# Função Única para Imagem (Placeholder para quando você escolher o provedor)
def generate_image(prompt):
    print(f"Solicitando imagem para: {prompt} usando o modelo {AIConfig.IMAGE_MODEL}")
    # Aqui entrará a lógica da API de imagem (OpenAI, Stability, etc)
    return "url_da_imagem_gerada.jpg"