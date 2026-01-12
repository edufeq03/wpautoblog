import os
import sys

# Adiciona a pasta raiz (um nível acima) ao caminho de busca do Python
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Agora seus imports funcionarão normalmente
from app import app
from models import db, User, Plan, PostLog, Blog
from services import content_service

def setup_test_data():
    """Configura dados de teste no banco de dados"""
    # 1. Criar um plano de teste (Limite de 2 posts por dia)
    plan = Plan.query.filter_by(name="Teste").first()
    if not plan:
        plan = Plan(name="Teste", posts_per_day=2, price=0)
        db.session.add(plan)
        db.session.commit()

    # 2. Criar um usuário de teste
    user = User.query.filter_by(email="tester@test.com").first()
    if not user:
        user = User(name="Tester", email="tester@test.com", password="123", plan_id=plan.id)
        db.session.add(user)
        db.session.commit()

    # 3. Criar um Blog para o usuário (necessário para o PostLog)
    blog = Blog.query.filter_by(user_id=user.id).first()
    if not blog:
        blog = Blog(user_id=user.id, site_name="Blog Teste", wp_url="http://teste.com", 
                    wp_user="admin", wp_app_password="123")
        db.session.add(blog)
        db.session.commit()
    
    return user, blog

def run_test():
    with app.app_context():
        print("\n=== INICIANDO TESTE DE TRAVAS DE PLANO ===\n")
        user, blog = setup_test_data()
        
        # Limpar logs antigos de teste para começar do zero
        PostLog.query.filter(PostLog.blog_id == blog.id).delete()
        db.session.commit()

        # TESTE 1: Verificar limite inicial (deve estar livre)
        reached, limit, current = content_service.user_reached_limit(user, is_ai_post=True)
        print(f"[TESTE 1] Inicial: {current}/{limit} posts. Bloqueado? {reached}")

        # TESTE 2: Simular primeira postagem
        log1 = PostLog(blog_id=blog.id, title="Post 1", status="Publicado", posted_at=datetime.now())
        db.session.add(log1)
        db.session.commit()
        
        reached, limit, current = content_service.user_reached_limit(user, is_ai_post=True)
        print(f"[TESTE 2] Após 1º post: {current}/{limit} posts. Bloqueado? {reached}")

        # TESTE 3: Simular segunda postagem (atingindo o limite de 2)
        log2 = PostLog(blog_id=blog.id, title="Post 2", status="Publicado", posted_at=datetime.now())
        db.session.add(log2)
        db.session.commit()
        
        reached, limit, current = content_service.user_reached_limit(user, is_ai_post=True)
        print(f"[TESTE 3] Após 2º post: {current}/{limit} posts. Bloqueado? {reached}")
        if reached:
            print(">>> SUCESSO: A trava funcionou ao atingir o limite!")

        # TESTE 4: Verificar se post MANUAL ignora a trava
        reached_manual, _, _ = content_service.user_reached_limit(user, is_ai_post=False)
        print(f"[TESTE 4] Post Manual: Bloqueado? {reached_manual} (Esperado: False)")
        
        if not reached_manual:
            print(">>> SUCESSO: Postagem manual continua liberada!")

        print("\n=== TESTE CONCLUÍDO ===")

if __name__ == "__main__":
    run_test()