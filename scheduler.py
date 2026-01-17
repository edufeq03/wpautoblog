import time
import schedule
import logging
from app import app
from models import db, ContentIdea
from services.content_service import publish_content_flow
import logging
import sys
import io

# Força o terminal a aceitar UTF-8 no Windows para evitar erro de emojis
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 1. Configuração de Logging Robusta com Encoding UTF-8 (SDD Requirement)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout), # Agora com sys.stdout forçado em UTF-8
        logging.FileHandler('scheduler.log', encoding='utf-8') # Salva em arquivo com UTF-8
    ]
)

# 1. Configuração de Logging Robusta (SDD Requirement)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scheduler.log') # Salva logs em arquivo para debug na VPS
    ]
)

def processar_fila_de_postagem():
    """
    Worker que processa posts pendentes. 
    Lógica: Busca o mais antigo -> Processa -> Marca Sucesso/Erro.
    """
    with app.app_context():
        try:
            # 1. Busca a tarefa 'pending' mais antiga
            tarefa = ContentIdea.query.filter_by(status='pending', is_posted=False).order_by(ContentIdea.created_at.asc()).first()

            if not tarefa:
                # Opcional: logging.info("Fila vazia. Aguardando...")
                return

            logging.info(f"🚀 Iniciando processamento: ID {tarefa.id} - {tarefa.title}")
            
            # 2. Verificação de integridade do relacionamento
            if not tarefa.blog:
                logging.error(f"❌ Erro: Tarefa {tarefa.id} não possui blog vinculado.")
                tarefa.status = 'failed'
                db.session.commit()
                return

            usuario = tarefa.blog.owner
            if not usuario:
                logging.error(f"❌ Erro: Proprietário não encontrado para o Blog {tarefa.blog.site_name}")
                tarefa.status = 'failed'
                db.session.commit()
                return

            # 3. Execução do Fluxo (IA -> WordPress)
            # timeout preventivo para evitar que o worker trave infinitamente
            sucesso, mensagem = publish_content_flow(tarefa, usuario)
            
            if sucesso:
                tarefa.status = 'completed'
                tarefa.is_posted = True
                logging.info(f"✅ SUCESSO: Post '{tarefa.title}' publicado no WP.")
            else:
                tarefa.status = 'failed'
                # Guardamos o erro no banco se possível ou apenas no log
                logging.error(f"⚠️ FALHA: {tarefa.title} | Motivo: {mensagem}")
            
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            logging.critical(f"🔥 ERRO CRÍTICO NO LOOP DO WORKER: {str(e)}")
            # Se houver uma tarefa presa no erro, marcamos como falha para não travar a fila
            try:
                if 'tarefa' in locals() and tarefa:
                    tarefa.status = 'failed'
                    db.session.commit()
            except:
                pass

# 4. Agendamento inteligente
# Verifica a cada 30 segundos. 
# Se um post demora 1 minuto para ser escrito pela IA, o próximo só começa após o término deste.
schedule.every(30).seconds.do(processar_fila_de_postagem)

if __name__ == "__main__":
    logging.info("=== 🤖 WORKER AUTOBLOG INICIADO ===")
    logging.info("Monitorando tabela 'content_idea' por status 'pending'...")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1) # Sleep curto para não sobrecarregar a CPU
    except KeyboardInterrupt:
        logging.info("=== 🛑 WORKER ENCERRADO PELO UTILIZADOR ===")
        sys.exit(0)