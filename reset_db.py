from app import app
from models import db, User, Plan, Blog
from werkzeug.security import generate_password_hash

def force_db_reset():
    with app.app_context():
        print("1. Conectando ao Postgres e removendo tabelas antigas...")
        db.drop_all()
        
        print("2. Criando novas tabelas...")
        db.create_all()
        
        print("3. Criando Planos Iniciais...")
        free = Plan(name='Free', max_sites=1, posts_per_day=1, price=0.0, credits_monthly=5)
        pro = Plan(name='Pro', max_sites=5, posts_per_day=10, price=97.0, credits_monthly=50, has_radar=True)
        vip = Plan(name='VIP', max_sites=15, posts_per_day=50, price=197.0, credits_monthly=200, has_radar=True, has_spy=True)
        db.session.add_all([free, pro, vip])
        db.session.commit()
        
        print("4. Criando Super Admin...")
        admin = User(
            email='admin@admin.com',
            password=generate_password_hash('123456', method='scrypt'),
            is_admin=True,
            plan_id=vip.id,
            credits=999
        )
        db.session.add(admin)
        
        print("5. Criando Usuário Demo...")
        demo = User(
            email='demo@wpautoblog.com.br',
            password=generate_password_hash('demo123', method='scrypt'),
            is_admin=False,
            plan_id=pro.id,
            credits=100
        )
        db.session.add(demo)
        
        db.session.commit()
        print("\n✅ SUCESSO: Postgres resetado. Admin e Planos criados!")

if __name__ == '__main__':
    force_db_reset()