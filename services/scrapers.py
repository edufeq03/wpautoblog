import requests
from bs4 import BeautifulSoup

def extrair_texto_da_url(url):
    """
    Extrai o conteúdo textual principal, simulando um navegador real 
    para evitar erros 403 (Forbidden).
    """
    try:
        # Cabeçalhos mais robustos para simular Chrome em Windows
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,/ ;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.google.com/',
            'DNT': '1' # Do Not Track
        }
        
        # Usamos uma sessão para manter cookies básicos se necessário
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        
        # Se ainda assim der erro, o site pode exigir ferramentas mais complexas (como Selenium)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Limpeza modular de ruído
        for tag in ["script", "style", "nav", "footer", "header", "aside", "form", "ads"]:
            for element in soup.find_all(tag):
                element.decompose()

        # Focamos em tags de texto que costumam conter o conteúdo do blog
        # Tentamos buscar primeiro dentro de uma tag <article> se existir
        corpo_artigo = soup.find('article') or soup
        paragrafos = corpo_artigo.find_all(['p', 'h2', 'h3'])
        
        texto_limpo = "\n".join([p.get_text().strip() for p in paragrafos if len(p.get_text()) > 30])
        
        return texto_limpo[:7000] # Limite para a Llama-3
        
    except requests.exceptions.HTTPError as e:
        print(f"Erro HTTP ao acessar {url}: {e}")
        return None
    except Exception as e:
        print(f"Erro inesperado no scraper: {e}")
        return None