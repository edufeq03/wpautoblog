from app import app
from models import db, User, Blog, Plan
from werkzeug.security import generate_password_hash

def force_db_reset():
    with app.app_context():
        print("1. Removendo todas as tabelas no Postgres...")
        db.drop_all()
        
        print("2. Criando novas tabelas...")
        db.create_all()
        
        print("3. Criando Planos...")
        free = Plan(name='Free', max_sites=1, posts_per_day=1, price=0.0)
        pro = Plan(name='Pro', max_sites=5, posts_per_day=10, price=97.0)
        vip = Plan(name='VIP', max_sites=15, posts_per_day=50, price=197.0)
        db.session.add_all([free, pro, vip])
        db.session.commit() # Salva para gerar IDs
        
        print("4. Criando usuário demo...")
        demo_user = User(
            email='demo@wpautoblog.com.br',
            password=generate_password_hash('demo123', method='scrypt'),
            plan_id=vip.id, # Usando ID real
            credits=100,
            is_admin=True # Definindo como admin para você testar
        )
        db.session.add(demo_user)
        db.session.commit()
        
        print("5. Criando blog para o demo...")
        site_demo = Blog(
            user_id=demo_user.id,
            site_name="Blog Demo",
            wp_url="https://wp.appmydream.com.br",
            wp_user="Maria",
            wp_app_password="qw5Z b2K3 NcIt oHkT nmg4 bpAe",
            macro_themes="Tecnologia",
            master_prompt="SEO Expert"
        )
        db.session.add(site_demo)
        db.session.commit()
        print("\n✅ BANCO POSTGRES ONLINE RESETADO COM SUCESSO!")

if __name__ == "__main__":
    force_db_reset()