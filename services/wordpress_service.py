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