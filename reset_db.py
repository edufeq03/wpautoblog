from app import app
from models import db, User, Blog
from werkzeug.security import generate_password_hash

def force_db_reset():
    with app.app_context():
        print("1. Removendo todas as tabelas antigas...")
        db.drop_all()
        
        print("2. Criando novas tabelas com a estrutura atualizada...")
        db.create_all()
        
        print("3. Criando usuário demo...")
        demo_user = User(
            email='demo@wpautoblog.com.br',
            password=generate_password_hash('demo123', method='pbkdf2:sha256'),
            plan_type='vip',
            credits=100,
            last_post_date=None
        )
        db.session.add(demo_user)
        db.session.commit()
        
        print("4. Criando blog inicial para o demo...")
        site_demo = Blog(
            user_id=demo_user.id,
            site_name="Blog Demo",
            wp_url="https://wp.appmydream.com.br",
            wp_user="Maria",
            wp_app_password="qw5Z b2K3 NcIt oHkT nmg4 bpAe",
            macro_themes="Tecnologia, Marketing",
            master_prompt="Escreva artigos focados em SEO..."
        )
        db.session.add(site_demo)
        db.session.commit()
        print("\n✅ Banco de dados resetado e usuário demo pronto!")

if __name__ == "__main__":
    force_db_reset()