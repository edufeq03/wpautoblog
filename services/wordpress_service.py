import requests
from requests.auth import HTTPBasicAuth

def post_to_wordpress(site, title, content, status='publish'):
    """Envia o conteúdo via REST API do WordPress."""
    wp_url = f"{site.wp_url}/wp-json/wp/v2/posts"
    auth = HTTPBasicAuth(site.wp_user, site.wp_app_password)
    
    payload = {
        'title': title,
        'content': content,
        'status': site.post_status or status,
        'categories': [] # Você pode expandir para ler a default_category
    }

    response = requests.post(wp_url, json=payload, auth=auth)
    return response.status_code == 201

def test_wp_connection(url, user, password):
    """
    Tenta autenticar no WordPress para validar as credenciais.
    Retorna (True, None) se sucesso, ou (False, "Mensagem de Erro").
    """
    # Remove barras extras no final da URL para evitar erro de caminho
    base_url = url.strip().rstrip('/')
    wp_api_url = f"{base_url}/wp-json/wp/v2/users/me"
    auth = HTTPBasicAuth(user, password)
    
    try:
        response = requests.get(wp_api_url, auth=auth, timeout=15)
        
        if response.status_code == 200:
            return True, "Conexão estabelecida com sucesso!"
        elif response.status_code == 401:
            return False, "Falha de autenticação: Usuário ou Senha de Aplicativo incorretos."
        elif response.status_code == 404:
            return False, "API REST não encontrada. Verifique se a URL do site está correta."
        else:
            return False, f"Erro inesperado (Status {response.status_code})."
            
    except requests.exceptions.RequestException as e:
        return False, f"Não foi possível conectar ao servidor: {str(e)}"
