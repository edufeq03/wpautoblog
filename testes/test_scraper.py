import requests
from bs4 import BeautifulSoup

def teste_manual(url):
    print(f"--- Testando URL: {url} ---")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove scripts e estilos
        for script in soup(["script", "style"]):
            script.decompose()

        texto = soup.get_text()
        linhas = (line.strip() for line in texto.splitlines())
        chunks = (phrase.strip() for line in linhas for phrase in line.split("  "))
        texto_limpo = '\n'.join(chunk for chunk in chunks if chunk)
        
        print("--- Conteúdo Extraído (primeiros 600 caracteres) ---")
        print(texto_limpo[:600])
        return True
    except Exception as e:
        print(f"ERRO CRÍTICO: {e}")
        return False

# Coloque uma URL de um blog aqui para testar
teste_manual("https://blog.pablomarcal.com.br/abandone-sem-do/")