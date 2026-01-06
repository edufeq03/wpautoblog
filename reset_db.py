from app import app
from models import db, User, Blog, Plan, ContentIdea, PostLog
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def force_db_reset():
    with app.app_context():
        print("1. Removendo todas as tabelas no Postgres...")
        db.drop_all() 
        
        print("2. Criando novas tabelas...")
        db.create_all()
        
        print("3. Criando Planos...")
        starter = Plan(name='Starter', max_sites=1, posts_per_day=1, price=0.0, has_images=False)
        lite    = Plan(name='Lite',    max_sites=3, posts_per_day=5, price=47.0, has_images=True)
        pro     = Plan(name='Pro',     max_sites=5, posts_per_day=10, price=97.0, has_images=True)
        vip     = Plan(name='VIP',     max_sites=15, posts_per_day=50, price=197.0, has_images=True)
        db.session.add_all([starter, lite, pro, vip])
        db.session.commit()
        
        print("4. Criando Super Admin...")
        admin_master = User(
            email='admin@admin.com',
            password=generate_password_hash('123456', method='scrypt'),
            plan_id=vip.id,
            credits=9999,
            is_admin=True
        )
        db.session.add(admin_master)
        
        print("5. Criando usuário demo e dados de exemplo...")
        demo_user = User(
            email='demo@wpautoblog.com.br',
            password=generate_password_hash('demo123', method='scrypt'),
            plan_id=vip.id,
            credits=100,
            is_admin=False # Deixe False para ele ver a interface de usuário comum
        )
        db.session.add(demo_user)
        db.session.commit() # Commit para gerar o ID do demo_user
        
        # 6. Criando blog para o demo
        site_demo = Blog(
            user_id=demo_user.id,
            site_name="Portal Tech Demo",
            wp_url="https://wp.appmydream.com.br",
            wp_user="Maria",
            wp_app_password="2319 GNlZ JIDx D606 yEOT YB7W",
            macro_themes="Inteligência Artificial, Gadgets, Futuro do Trabalho",
            master_prompt="Você é um redator sênior de tecnologia focado em SEO."
        )
        db.session.add(site_demo)
        db.session.commit()

        print("7. Populando histórico de demonstração...")
        # Adiciona algumas ideias na fila
        ideias = [
            "Como a IA vai mudar o marketing em 2026",
            "5 Gadgets que você precisa conhecer este mês",
            "O guia definitivo do trabalho remoto"
        ]
        for titulo in ideias:
            db.session.add(ContentIdea(title=titulo, blog_id=site_demo.id))

        # Adiciona alguns logs de posts já "feitos"
        log1 = PostLog(
            blog_id=site_demo.id,
            title="A Revolução dos Carros Elétricos",
            status="Publicado",
            wp_post_id=123,
            post_url="#",
            posted_at=datetime.utcnow() - timedelta(days=1)
        )
        db.session.add(log1)
        
        db.session.commit()
        
        print("\n✅ SUCESSO: Banco resetado e Ambiente Demo pronto!")
        print(f"Login Demo: {demo_user.email} | Senha: demo123")

if __name__ == "__main__":
    force_db_reset()