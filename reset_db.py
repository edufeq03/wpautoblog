from app import app
from models import db, User, Blog, Plan, ContentIdea, PostLog
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta, UTC

def force_db_reset():
    with app.app_context():
        print("1. Reiniciando Banco de Dados...")
        db.drop_all() 
        db.create_all()
        
        print("2. Criando Planos...")
        starter = Plan(name='Starter', max_sites=1, posts_per_day=1, price=0.0, has_images=False)
        lite    = Plan(name='Lite',    max_sites=1, posts_per_day=2, price=47.0, has_images=True)
        pro     = Plan(name='Pro',     max_sites=3, posts_per_day=15, price=97.0, has_images=True)
        vip     = Plan(name='VIP',     max_sites=15, posts_per_day=50, price=397.0, has_images=True)
        db.session.add_all([starter, lite, pro, vip])
        db.session.commit()
        
        print("3. Criando Usuários (Admin e Demo)...")
        # Admin Real
        admin_master = User(
            name='Admin Master',
            email='admin@admin.com',
            password=generate_password_hash('senha123', method='pbkdf2:sha256'),
            plan_id=vip.id
        )
        # Usuário Demo
        demo_user = User(
            name='Visitante Demo',
            email='demo@wpautoblog.com',
            password=generate_password_hash('demo123', method='pbkdf2:sha256'),
            plan_id=vip.id # Demo vê tudo liberado
        )
        db.session.add_all([admin_master, demo_user])
        db.session.commit()

        print("4. Criando Site de Demonstração...")
        site_demo = Blog(
            user_id=demo_user.id,
            site_name="Portal Tech Demo",
            wp_url="https://wp.appmydream.com.br",
            wp_user="Maria",
            wp_app_password="XXXX XXXX XXXX XXXX",
            macro_themes="IA, Gadgets, Futuro do Trabalho",
            master_prompt="Você é um redator sênior de tecnologia focado em SEO.",
            schedule_time="09:00",
            posts_per_day=3,
            post_status="publish"
        )
        db.session.add(site_demo)
        db.session.commit()

        print("5. Gerando Histórico Fictício para Gráficos...")
        # Criar posts nos últimos 7 dias para o gráfico do Dashboard não ficar vazio
        titulos_exemplo = [
            "O impacto do GPT-5 no mercado", "Novos MacBooks 2026", 
            "Como automatizar blogs", "Segurança em APIs", "DALL-E 3 vs Midjourney"
        ]
        
        for i in range(7):
            data_post = datetime.now(UTC) - timedelta(days=i)
            log = PostLog(
                blog_id=site_demo.id,
                title=titulos_exemplo[i % len(titulos_exemplo)],
                status="Publicado",
                post_url="#",
                posted_at=data_post
            )
            db.session.add(log)
        
        print("6. Populando Fila de Ideias...")
        ideias = [
            "As 10 melhores ferramentas de IA de 2026",
            "Trabalho remoto: O fim dos escritórios?",
            "Guia de SEO para iniciantes"
        ]
        for t in ideias:
            db.session.add(ContentIdea(title=t, blog_id=site_demo.id))
            
        db.session.commit()
        print("✅ Banco Resetado e Demo Pronta!")

if __name__ == "__main__":
    force_db_reset()