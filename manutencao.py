from app import app
from models import db, ContentIdea

def limpar_ideias_corrompidas():
    # Isso cria o 'contexto' que o Flask pediu no erro
    with app.app_context():
        print("🔍 Procurando ideias sem blog_id...")
        
        # Busca a quantidade antes de deletar para te dar um feedback
        corrompidas = ContentIdea.query.filter_by(blog_id=None).all()
        total = len(corrompidas)
        
        if total > 0:
            print(f"⚠️ Encontradas {total} ideias inválidas. Removendo...")
            try:
                # Executa a deleção
                ContentIdea.query.filter_by(blog_id=None).delete()
                db.session.commit()
                print("✅ Sucesso! O banco de dados está limpo.")
            except Exception as e:
                db.session.rollback()
                print(f"❌ Erro ao limpar banco: {e}")
        else:
            print("✨ Nada para limpar! Todas as ideias estão vinculadas a um site.")

if __name__ == "__main__":
    limpar_ideias_corrompidas()