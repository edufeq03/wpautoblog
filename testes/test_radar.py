import sys
import os

# Adiciona a raiz do projeto ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from services.scraper_service import extrair_texto_da_url
from services.ai_service import generate_text

def test_fluxo_radar():
    print("\n=== INICIANDO TESTE DE RADAR (CAPTURADOR) ===")
    
    # URL de teste (use uma notícia real de tecnologia ou marketing)
    url_teste = "https://g1.globo.com/tecnologia/" 
    
    print(f"1. Tentando ler a URL: {url_teste}")
    texto_puro = extrair_texto_da_url(url_teste)
    
    if not texto_puro:
        print("❌ FALHA: O scraper foi bloqueado ou a URL é inválida.")
        return

    print(f"✅ SUCESSO: Capturado {len(texto_puro)} caracteres.")
    print(f"Snippet do texto limpo: {texto_puro[:200]}...")

    # 2. Testando a inteligência do Radar (Análise)
    print("\n2. Enviando para IA analisar e sugerir 3 títulos SEO...")
    
    prompt = (
        "Com base no texto extraído de um site de notícias abaixo, "
        "identifique o tema principal e sugira 3 títulos de posts virais para blog. "
        "Retorne apenas os títulos.\n\n"
        f"TEXTO: {texto_puro[:3000]}"
    )

    with app.app_context():
        try:
            sugestoes = generate_text(prompt)
            if sugestoes:
                print("✅ IA RESPONDEU COM SUCESSO:")
                print("-" * 30)
                print(sugestoes)
                print("-" * 30)
            else:
                print("❌ FALHA: A IA retornou vazio.")
        except Exception as e:
            print(f"❌ ERRO NA API DE IA: {e}")

if __name__ == "__main__":
    test_fluxo_radar()