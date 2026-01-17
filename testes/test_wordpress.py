import sys
import os
import requests
from requests.auth import HTTPBasicAuth

# Adiciona a raiz do projeto ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, Blog

def test_conexao_wordpress():
    print("\n=== INICIANDO TESTE DE CONEXÃO WORDPRESS ===")

    with app.app_context():
        # 1. Busca o primeiro blog cadastrado
        # blog = Blog.query.first()
        blog = Blog.query.get(2)
        
        if not blog:
            print("❌ ERRO: Nenhum blog cadastrado no banco para testar.")
            return

        print(f"Testando site: {blog.wp_url}")
        print(f"Usuário: {blog.wp_user}")
        
        # Limpa a URL (remove barras no final)
        base_url = blog.wp_url.rstrip('/')
        api_url = f"{base_url}/wp-json/wp/v2/posts"
        
        # 2. Configura a Autenticação (Application Password)
        auth = HTTPBasicAuth(blog.wp_user, blog.wp_app_password)
        
        # Payload de teste
        payload = {
            'title': 'Post de Teste - Sistema de Monitorização',
            'content': 'Se estás a ler isto, a integração do teu AutoBlog está a funcionar 100%!',
            'status': 'draft' # Enviamos como rascunho para não poluir o site
        }

        print("Enviando requisição para a API do WordPress...")
        
        try:
            response = requests.post(api_url, auth=auth, json=payload, timeout=20)
            
            if response.status_code in [200, 201]:
                print("✅ SUCESSO TOTAL! O post foi criado com sucesso.")
                print(f"Link do rascunho: {response.json().get('link')}")
            
            elif response.status_code == 401:
                print("❌ ERRO 401: Falha na autenticação. Verifica a 'Application Password' (Senha de Aplicação).")
                print("Dica: Não é a senha de login, é a senha gerada no perfil do usuário no WP.")
            
            elif response.status_code == 404:
                print("❌ ERRO 404: API não encontrada. Verifica se o site usa links permanentes (Permalinks) como 'Nome do Post'.")
            
            else:
                print(f"❌ ERRO {response.status_code}: O WordPress recusou a conexão.")
                print(f"Resposta: {response.text}")

        except Exception as e:
            print(f"❌ ERRO CRÍTICO DE REDE: {str(e)}")

if __name__ == "__main__":
    test_conexao_wordpress()