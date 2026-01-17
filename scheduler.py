import time
import schedule
import logging
import sys
import io
from datetime import datetime, date
from app import app
from models import db, Blog, ContentIdea
from services.content_service import publish_content_flow

# Ajuste de codificação para evitar erros de Emoji no Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scheduler.log', encoding='utf-8')
    ]
)

def check_and_enqueue_auto_posts():
    """
    SISTEMA DE DECISÃO:
    Varre os blogs e move ideias de 'draft' para 'pending' conforme o horário.
    """
    with app.app_context():
        hoje = date.today()
        agora_hora = datetime.now().strftime("%H:%M")
        
        logging.info(f"🕒 Verificando cronogramas (Hora atual: {agora_hora})...")
        
        blogs = Blog.query.all()
        for blog in blogs:
            # Verifica se atingiu o horário configurado pelo usuário
            if agora_hora >= blog.schedule_time:
                
                # Conta quantos posts já foram enfileirados ou feitos hoje
                posts_hoje = ContentIdea.query.filter(
                    ContentIdea.blog_id == blog.id,
                    db.func.date(ContentIdea.created_at) == hoje,
                    ContentIdea.status.in_(['pending', 'completed'])
                ).count()

                if posts_hoje < (blog.posts_per_day or 1):
                    # Seleciona a próxima ideia 'draft' disponível
                    proxima = ContentIdea.query.filter_by(
                        blog_id=blog.id, 
                        status='draft',
                        is_posted=False
                    ).order_by(ContentIdea.created_at.asc()).first()

                    if proxima:
                        logging.info(f"🤖 [AGENDADOR] Ativando post: '{proxima.title}' para o blog {blog.site_name}")
                        proxima.status = 'pending'
                        proxima.created_at = datetime.now() # Atualiza para contar no limite de hoje
                        db.session.commit()

def processar_fila_de_postagem():
    with app.app_context():
        # Pegamos apenas um por vez, o mais antigo
        tarefa = ContentIdea.query.filter_by(status='pending', is_posted=False).first()

        if tarefa:
            # BLOQUEIO PREVENTIVO: Mudamos o status ANTES de começar o trabalho pesado
            tarefa.status = 'processing' 
            db.session.commit()
            
            try:
                sucesso, mensagem = publish_content_flow(tarefa, tarefa.blog.owner)
                
                if sucesso:
                    tarefa.status = 'completed'
                    tarefa.is_posted = True
                else:
                    tarefa.status = 'failed'
                    # Opcional: registrar a mensagem de erro no PostLog
                
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                tarefa.status = 'failed' # Libera a fila em caso de erro grave
                db.session.commit()

# --- DEFINIÇÃO DOS CICLOS ---

# 1. Tenta processar a fila a cada 30 segundos
schedule.every(30).seconds.do(processar_fila_de_postagem)

# 2. Tenta agendar novos posts a cada 5 minutos (evita duplicatas no mesmo minuto)
schedule.every(5).minutes.do(check_and_enqueue_auto_posts)

if __name__ == "__main__":
    logging.info("=== 🤖 SISTEMA DE AUTOMAÇÃO AUTOBLOG INICIADO ===")
    
    # Roda uma verificação inicial ao ligar
    check_and_enqueue_auto_posts()
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("🛑 Encerrado manualmente.")