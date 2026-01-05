import requests
from openai import OpenAI
import os

def processar_imagem_featured(titulo_post, wp_url, auth_wp):
    """
    Gera uma imagem via DALL-E 3 e faz o upload para o WordPress.
    """
    # 0. Configuração do Cliente
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Erro: OPENAI_API_KEY não encontrada.")
        return None
        
    client = OpenAI(api_key=api_key)
    wp_url = wp_url.rstrip('/') # Remove barra extra se houver

    try:
        # 1. Gerar o Prompt Visual (Como o nó 'Criador Posts' do n8n)
        prompt_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user", 
                "content": f"Crie um prompt detalhado para o DALL-E 3 gerar uma imagem de destaque estilo fotografia profissional para um post de blog com o título: {titulo_post}. Não inclua textos na imagem."
            }]
        )
        visual_prompt = prompt_response.choices[0].message.content

        # 2. Gerar a Imagem (Nó DALL-E do n8n)
        image_gen = client.images.generate(
            model="dall-e-3",
            prompt=visual_prompt,
            n=1,
            size="1024x1024"
        )
        image_url = image_gen.data[0].url

        # 3. Download da Imagem
        img_res = requests.get(image_url)
        if img_res.status_code != 200:
            return None
        img_data = img_res.content

        # 4. Upload para o WordPress (Nó 'UploadImage')
        headers = {
            'Content-Disposition': f'attachment; filename="featured_{os.urandom(2).hex()}.jpg"',
            'Content-Type': 'image/jpeg'
        }
        
        response = requests.post(
            f"{wp_url}/wp-json/wp/v2/media",
            auth=auth_wp,
            headers=headers,
            data=img_data
        )
        
        if response.status_code == 201:
            return response.json().get('id')
        
        print(f"Erro WP Media: {response.text}")
        return None

    except Exception as e:
        print(f"Erro no processamento de imagem: {str(e)}")
        return None