import os
import sys
from dotenv import load_dotenv

# AJUSTE DE CAMINHO: Adiciona a raiz do projeto ao path do Python
raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if raiz not in sys.path:
    sys.path.insert(0, raiz)

from services.image_service import processar_imagem_featured

# Carrega as variáveis do .env
load_dotenv()

def testar_geracao_e_upload():
    print("🚀 Iniciando teste de imagem...")
    
    # --- DADOS DE TESTE (Preencha com dados reais de um site seu) ---
    titulo_teste = "Como a Inteligência Artificial está mudando o Marketing Digital"
    wp_url="https://blog.appmydream.com.br"
    wp_user="MCarolina"
    wp_app_password="65tv YZO4 mrbJ M9HB 4gTs OQhl"
    auth_wp = (wp_user, wp_app_password)

    try:
        print(f"🎨 Gerando imagem para o título: '{titulo_teste}'...")
        # Chama a função que criamos no image_service
        id_imagem = processar_imagem_featured(titulo_teste, wp_url, auth_wp)
        
        if id_imagem:
            print(f"✅ SUCESSO! Imagem enviada para o WordPress.")
            print(f"🆔 ID da Mídia no WordPress: {id_imagem}")
            print(f"🔗 Verifique na sua biblioteca de mídia do WP: {wp_url}/wp-admin/upload.php")
        else:
            print("❌ A função retornou None. Verifique os logs acima.")
            
    except Exception as e:
        print(f"💥 ERRO CRÍTICO no teste: {str(e)}")

if __name__ == "__main__":
    testar_geracao_e_upload()