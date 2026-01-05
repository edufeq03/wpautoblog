import requests
from openai import OpenAI
import os
from services.ai_service import criar_prompt_visual

def processar_imagem_featured(titulo_post, wp_url, auth_wp):
    print(f"\n--- [SERVICE DEBUG] Iniciando processamento ---")
    # Limpeza de ambiente para evitar erro de proxies
    for key in list(os.environ.keys()):
        if "PROXY" in key.upper():
            print(f"DEBUG: Removendo variável de ambiente: {key}")
            os.environ.pop(key)

    api_key = os.environ.get("OPENAI_API_KEY")
    print(f"DEBUG: OpenAI Key detectada? {'Sim' if api_key else 'Não'}")
    
    try:
        client = OpenAI(api_key=api_key)
        
        print(f"DEBUG: Solicitando prompt visual ao ai_service...")
        visual_prompt = criar_prompt_visual(titulo_post)
        print(f"DEBUG: Prompt gerado: {visual_prompt[:50]}...")

        print("DEBUG: Chamando API DALL-E 3...")
        image_gen = client.images.generate(
            model="dall-e-3",
            prompt=visual_prompt,
            n=1,
            size="1024x1024"
        )
        image_url = image_gen.data[0].url
        print(f"DEBUG: URL da imagem recebida com sucesso.")

        print(f"DEBUG: Fazendo download da imagem...")
        img_res = requests.get(image_url, timeout=30)
        print(f"DEBUG: Status download: {img_res.status_code}")

        print(f"DEBUG: Fazendo upload para WordPress em: {wp_url}")
        headers = {
            'Content-Disposition': f'attachment; filename="f_{os.urandom(2).hex()}.jpg"',
            'Content-Type': 'image/jpeg'
        }
        response = requests.post(
            f"{wp_url.rstrip('/')}/wp-json/wp/v2/media",
            auth=auth_wp,
            headers=headers,
            data=img_res.content,
            timeout=60
        )
        print(f"DEBUG: Resposta WP Media Status: {response.status_code}")
        
        if response.status_code == 201:
            media_id = response.json().get('id')
            print(f"DEBUG: Sucesso total! ID gerado: {media_id}")
            return media_id
        
        print(f"DEBUG: Falha no WP. Resposta: {response.text}")
        return None

    except Exception as e:
        print(f"DEBUG: EXCEÇÃO NO SERVICE: {str(e)}")
        return None