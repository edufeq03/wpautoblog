import requests
from bs4 import BeautifulSoup

def extrair_texto_da_url(url):
    """
    Extrai o conteúdo principal de uma URL simulando um navegador real.
    """
    # Cabeçalhos para simular um navegador Chrome no Windows
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Referer': 'https://www.google.com/'
    }

    # No scraper_service.py, dentro da função extrair_texto_da_url

    # 1. Tags para remover completamente
    tags_para_remover = [
        'script', 'style', 'nav', 'footer', 'header', 'aside', 
        'form', 'iframe', 'noscript', 'svg', 'button'
    ]
    for element in soup(tags_para_remover):
        element.decompose()

    # 2. Remover classes e IDs comuns de publicidade e menus (Opcional, mas potente)
    lixo_seletivo = [
        'cookie', 'banner', 'ads', 'sidebar', 'social-share', 'menu'
    ]
    for tag in soup.find_all(True, {'class': True}):
        if any(lixo in ' '.join(tag['class']).lower() for lixo in lixo_seletivo):
            tag.decompose()

    try:
        # Timeout curto para não travar o sistema (15 segundos)
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() # Levanta erro se for 403, 404, 500, etc.
        
        # Define a codificação correta para evitar caracteres estranhos
        response.encoding = response.apparent_encoding 
        
        soup = BeautifulSoup(response.text, 'html.parser')

        # Remove elementos irrelevantes para o post
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
            element.decompose()

        # Pega o texto limpo
        texto = soup.get_text(separator=' ')
        
        # Limpeza de espaços excessivos
        linhas = (line.strip() for line in texto.splitlines())
        chunks = (phrase.strip() for line in linhas for phrase in line.split("  "))
        texto_limpo = '\n'.join(chunk for chunk in chunks if chunk)

        return texto_limpo[:10000] # Limite de segurança para a API de IA

    except Exception as e:
        print(f">>> [ERRO SCRAPER] Falha ao ler {url}: {str(e)}")
        return None