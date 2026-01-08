# services/scraper_service.py
import requests
from bs4 import BeautifulSoup

def extrair_texto_da_url(url):
    """
    Extrai o conteúdo textual principal de uma URL, simulando um navegador real.
    Retorna o texto limpo ou None se houver falha.
    """
    if not url:
        return None

    try:
        # Cabeçalhos robustos para simular um navegador real (evita erro 403)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.google.com/',
            'DNT': '1'
        }
        
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        
        # Verifica se o request foi bem sucedido
        response.raise_for_status()
        
        # Força o encoding correto se o site não informar
        if response.encoding == 'ISO-8859-1':
            response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Limpeza de ruído (elementos que não são conteúdo)
        for tag in ["script", "style", "nav", "footer", "header", "aside", "form", "ads", "iframe"]:
            for element in soup.find_all(tag):
                element.decompose()

        # Focamos na parte central do conteúdo
        # Muitas vezes os blogs usam a tag <article> ou <main>
        corpo_artigo = soup.find('article') or soup.find('main') or soup.find('div', {'class': 'content'}) or soup
        
        # Pegamos parágrafos e títulos para manter a estrutura do texto
        paragrafos = corpo_artigo.find_all(['p', 'h1', 'h2', 'h3'])
        
        # Filtramos textos muito curtos (que costumam ser legendas ou botões)
        texto_limpo = "\n".join([p.get_text().strip() for p in paragrafos if len(p.get_text().strip()) > 30])
        
        return texto_limpo if texto_limpo else None

    except requests.exceptions.RequestException as e:
        print(f"❌ Erro de conexão ao acessar {url}: {e}")
        return None
    except Exception as e:
        print(f"❌ Erro inesperado ao extrair texto: {e}")
        return None