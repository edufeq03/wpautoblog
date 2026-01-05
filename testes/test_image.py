import os
import sys
from dotenv import load_dotenv

# 1. Ajuste de Caminho: Garante que o Python encontre a pasta 'services'
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

# Importa a limpeza de ambiente para evitar o erro de proxies antes de qualquer coisa
def limpar_ambiente():
    for key in list(os.environ.keys()):
        if "PROXY" in key.upper():
            os.environ.pop(key)

limpar_ambiente()

# Carrega as variáveis do .env explicitamente
load_dotenv(os.path.join(raiz, '.env'))

# Agora importamos o serviço
from services.image_service import processar_imagem_featured

def testar_geracao_e_upload():
    print("\n🚀 [FASE 1] Iniciando teste de imagem com LangChain + Groq...")

    # --- VERIFICAÇÃO DE VARIÁVEIS CRÍTICAS ---
    # O erro 'Input should be a valid string' ocorre se estas variáveis forem None
    groq_main = os.environ.get("GROQ_MODEL_MAIN")
    groq_quick = os.environ.get("GROQ_MODEL_QUICK")
    
    if not groq_main or not groq_quick:
        print("❌ ERRO: Variáveis de modelo do Groq não encontradas no .env!")
        print(f"DEBUG: GROQ_MODEL_MAIN={groq_main}, GROQ_MODEL_QUICK={groq_quick}")
        return

    # --- DADOS DE TESTE ---
    titulo_teste = "Como alimentar uma capivara sem risco de ser mordido"
    wp_url = "https://blog.appmydream.com.br"
    wp_user = "MCarolina"
    wp_app_password = "65tv YZO4 mrbJ M9HB 4gTs OQhl"
    auth_wp = (wp_user, wp_app_password)

    try:
        print(f"🎨 [FASE 2] Gerando prompt (Groq) e Imagem (DALL-E) para: '{titulo_teste}'...")
        
        # Chama a função que agora usa LangChain internamente
        id_imagem = processar_imagem_featured(titulo_teste, wp_url, auth_wp)
        
        if id_imagem:
            print(f"✅ [SUCESSO] Imagem enviada para o WordPress!")
            print(f"🆔 ID da Mídia: {id_imagem}")
            print(f"🔗 Confira em: {wp_url}/wp-admin/upload.php")
        else:
            print("❌ [FALHA] A função retornou None. Verifique as mensagens de erro acima.")
            
    except Exception as e:
        print(f"💥 [ERRO CRÍTICO] Falha inesperada: {str(e)}")

if __name__ == "__main__":
    testar_geracao_e_upload()