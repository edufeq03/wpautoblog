import time
import schedule
import logging
from app import app
from models import db, ContentIdea
from services.content_service import publish_content_flow

# Configuração de logs profissional
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def processar_fila_de_postagem():
    """
    Worker que processa posts pendentes um por um para evitar sobrecarga.
    """
    with app.app_context():
        # 1. Busca a tarefa pendente mais antiga (FIFO)
        tarefa = ContentIdea.query.filter_by(status='pending', is_posted=False).first()

        if not tarefa:
            return

        logging.info(f"--- Processando ID {tarefa.id}: {tarefa.title} ---")
        
        try:
            # 2. Identifica o dono do post através do relacionamento 'owner'
            # O log anterior confirmou que 'owner' é o relacionamento ativo no seu model
            usuario = tarefa.blog.owner

            if not usuario:
                logging.error(f"❌ Usuário não encontrado para o blog ID {tarefa.blog_id}")
                tarefa.status = 'failed'
                db.session.commit()
                return

            # 3. Executa o fluxo de publicação (IA -> Imagem -> WordPress)
            sucesso, mensagem = publish_content_flow(tarefa, usuario)
            
            if sucesso:
                tarefa.status = 'completed'
                tarefa.is_posted = True
                logging.info(f"✅ SUCESSO: {tarefa.title}")
            else:
                tarefa.status = 'failed'
                logging.error(f"❌ FALHA NO WP: {mensagem}")
            
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            # Marca como falha para não entrar em loop infinito de erro
            if tarefa:
                tarefa.status = 'failed'
                db.session.commit()
            logging.critical(f"⚠️ ERRO CRÍTICO NO WORKER: {str(e)}")

# Intervalo de 30 segundos entre tentativas de processamento
schedule.every(30).seconds.do(processar_fila_de_postagem)

if __name__ == "__main__":
    logging.info("=== WORKER AUTOBLOG ATIVO (Aguardando status 'pending') ===")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Worker encerrado manualmente.")