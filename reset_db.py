from app import app
from models import db, User, Blog, Plan
from werkzeug.security import generate_password_hash

def force_db_reset():
    with app.app_context():
        # O timeout pode acontecer aqui se a conexão estiver lenta ou bloqueada
        print("1. Removendo todas as tabelas no Postgres...")
        db.drop_all() 
        
        print("2. Criando novas tabelas...")
        db.create_all()
        
        print("3. Criando Planos Base...")
        print("3. Criando Planos...")
        starter = Plan(name='Starter', max_sites=1, posts_per_day=1, price=0.0)
        lite    = Plan(name='Lite',    max_sites=3, posts_per_day=5, price=47.0)
        pro     = Plan(name='Pro',     max_sites=5, posts_per_day=10, price=97.0)
        vip     = Plan(name='VIP',     max_sites=15, posts_per_day=50, price=197.0)
        db.session.add_all([starter, lite, pro, vip])
        db.session.commit()
        
        print("4. Criando Super Admin (Acesso Total)...")
        # Criando o seu usuário administrador principal
        admin_master = User(
            email='admin@admin.com',
            password=generate_password_hash('123456', method='scrypt'),
            plan_id=vip.id,
            credits=9999,
            is_admin=True
        )
        db.session.add(admin_master)
        
        print("5. Criando usuário demo...")
        demo_user = User(
            email='demo@wpautoblog.com.br',
            password=generate_password_hash('demo123', method='scrypt'),
            plan_id=vip.id,
            credits=100,
            is_admin=True # Definido como admin para facilitar seus testes
        )
        db.session.add(demo_user)
        db.session.commit()
        
        print("6. Criando blog para o demo...")
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
        
        print("\n✅ SUCESSO: Banco resetado e Admin criado!")
        print("Login Admin: admin@admin.com | Senha: 123456")

if __name__ == "__main__":
    force_db_reset()