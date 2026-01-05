import requests
from openai import OpenAI
import os

def processar_imagem_featured(titulo_post, wp_url, auth_wp):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Erro: OPENAI_API_KEY não encontrada.")
        return None
        
    # Inicialização simples para evitar erro de 'proxies'
    client = OpenAI(api_key=api_key)
    wp_url = wp_url.rstrip('/') 

    try:
        # 1. Gerar o Prompt Visual
        prompt_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"Crie um prompt para o DALL-E 3 gerar uma imagem profissional para: {titulo_post}"}]
        )
        visual_prompt = prompt_response.choices[0].message.content

        # 2. Gerar a Imagem
        image_gen = client.images.generate(
            model="dall-e-3",
            prompt=visual_prompt,
            n=1,
            size="1024x1024"
        )
        image_url = image_gen.data[0].url

        # 3. Download com Timeout
        img_res = requests.get(image_url, timeout=30) # Adicionado timeout
        if img_res.status_code != 200:
            return None
        img_data = img_res.content

        # 4. Upload para o WordPress
        headers = {
            'Content-Disposition': f'attachment; filename="featured_{os.urandom(2).hex()}.jpg"',
            'Content-Type': 'image/jpeg'
        }
        
        response = requests.post(
            f"{wp_url}/wp-json/wp/v2/media",
            auth=auth_wp,
            headers=headers,
            data=img_data,
            timeout=60 # Adicionado timeout
        )
        
        if response.status_code == 201:
            return response.json().get('id')
        
        return None
    except Exception as e:
        print(f"Erro no serviço de imagem: {str(e)}")
        return None