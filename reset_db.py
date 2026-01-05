from app import app
from models import db, User, Blog, Plan
from werkzeug.security import generate_password_hash

def force_db_reset():
    with app.app_context():
        print("1. Limpando banco de dados...")
        db.drop_all()
        db.create_all()
        
        print("2. Criando Planos Iniciais...")
        # Definindo os planos base do sistema
        free = Plan(name='Free', max_sites=1, posts_per_day=1, price=0.0, credits_monthly=5)
        pro = Plan(name='Pro', max_sites=5, posts_per_day=10, price=97.0, credits_monthly=50, has_radar=True)
        vip = Plan(name='VIP', max_sites=15, posts_per_day=50, price=197.0, credits_monthly=200, has_radar=True, has_spy=True)
        
        db.session.add_all([free, pro, vip])
        db.session.commit() # Salvamos os planos primeiro
        
        print("3. Criando Super Admin...")
        admin = User(
            email='admin@admin.com',
            password=generate_password_hash('123456', method='scrypt'),
            is_admin=True,
            plan_id=vip.id, # Vincula ao plano VIP criado acima
            credits=999
        )
        db.session.add(admin)
        
        print("4. Criando Usuário Demo...")
        demo = User(
            email='demo@wpautoblog.com.br',
            password=generate_password_hash('demo123', method='scrypt'),
            is_admin=False,
            plan_id=pro.id,
            credits=100
        )
        db.session.add(demo)
        
        try:
            db.session.commit()
            print("Sucesso! Banco de dados resetado com Planos e Admin.")
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao salvar usuários: {e}")

if __name__ == '__main__':
    force_db_reset()