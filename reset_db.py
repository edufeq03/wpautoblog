from app import app, db
# Importe todos os seus modelos aqui para que o SQLAlchemy os reconheça
from models import Blog, ContentSource, ContentIdea, CapturedContent 

with app.app_context():
    print("Limpando banco de dados...")
    db.drop_all()
    print("Criando novas tabelas...")
    db.create_all()
    print("Banco de dados resetado com sucesso!")