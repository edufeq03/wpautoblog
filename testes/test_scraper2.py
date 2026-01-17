import sys
import os

# Adiciona a raiz do projeto ao caminho de busca do Python
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.scraper_service import extrair_texto_da_url

def executar_teste():
    url = "https://www.uol.com.br/" # Substitua por uma URL real para o teste
    print(f"Iniciando teste de extração: {url}")
    
    texto = extrair_texto_da_url(url)
    
    if texto and len(texto) > 100:
        print("✅ SUCESSO: Conteúdo extraído com sucesso!")
        print(f"Snippet: {texto[:650]}...")
    else:
        print("❌ FALHA: O scraper não conseguiu ler o conteúdo.")

if __name__ == "__main__":
    executar_teste()