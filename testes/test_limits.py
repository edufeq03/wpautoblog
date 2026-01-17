import sys
import os
from datetime import date

# Adiciona a raiz do projeto ao path para encontrar models e app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, User, PostLog, Blog

def test_limites_diarios():
    with app.app_context():
        # 1. Busca um usuário e seu blog para o teste
        user = User.query.first()
        blog = Blog.query.filter_by(user_id=user.id).first()
        
        if not user or not blog:
            print("❌ Erro: Usuário ou Blog não encontrados para o teste.")
            return

        print(f"\n--- Testando Limites Diários para: {user.email} ---")

        # 2. Configura um cenário controlado
        # Vamos definir o limite do plano para apenas 2 posts por dia
        if user.plan:
            user.plan.posts_per_day = 2
            db.session.commit()
            print(f"Limite do plano definido para: {user.plan.posts_per_day} posts/dia")
        else:
            print("⚠️ Usuário sem plano associado. O teste pode falhar na lógica de limite.")
            return

        # 3. Limpa logs de hoje para começar do zero (no contexto deste teste)
        PostLog.query.filter(
            PostLog.blog_id == blog.id, 
            db.func.date(PostLog.posted_at) == date.today()
        ).delete()
        db.session.commit()

        # 4. Simula o preenchimento do limite
        print("Simulando 2 postagens já realizadas hoje...")
        for i in range(2):
            log = PostLog(blog_id=blog.id, title=f"Post Teste {i}", status="Publicado")
            db.session.add(log)
        db.session.commit()

        # 5. Executa a verificação de limite (Método que refatoramos para a classe User)
        print("Verificando se o limite bloqueia a 3ª postagem...")
        reached, limit, current = user.reached_daily_limit(is_ai_post=True)

        if reached:
            print(f"✅ SUCESSO: O sistema bloqueou corretamente. ({current}/{limit})")
        else:
            print(f"❌ FALHA: O sistema permitiu postar além do limite! ({current}/{limit})")

        # 6. Teste de Bypass para Admin
        print("\nTestando se Admin ignora o limite...")
        original_status = user.is_admin
        user.is_admin = True
        reached_admin, _, _ = user.reached_daily_limit(is_ai_post=True)
        
        if not reached_admin:
            print("✅ SUCESSO: Admin ignorou o limite corretamente.")
        else:
            print("❌ FALHA: Admin foi bloqueado pelo limite.")

        # Limpeza final (Rollback para não afetar dados reais se preferir)
        user.is_admin = original_status
        db.session.rollback() 
        print("\n--- Teste de limites concluído ---")

if __name__ == "__main__":
    test_limites_diarios()