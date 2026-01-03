from flask import Flask
from models import db, login_manager
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from flask_apscheduler import APScheduler
import os

# Importe a função que percorre o Radar
from utils.ai_logic import processar_radar_automatico 

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# AJUSTE 1: Usa a chave do ambiente, ou a chave do .env local como fallback
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.environ.get('FLASK_SECRET_KEY', 'chave-padrao'))
# AJUSTE 2: Usa a DATABASE_URL do ambiente (Essencial para o Easypanel)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')


# --- INICIALIZAÇÃO DE PLUGINS ---
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# --- AGENDADOR (Scheduler) ---
scheduler = APScheduler()
app.config['SCHEDULER_API_ENABLED'] = True
scheduler.init_app(app)
scheduler.start()

# Tarefa Agendada: Sincronizar Radar a cada 12 horas
@scheduler.task('interval', id='sync_radar_job', hours=12)
def scheduled_radar_sync():
    with app.app_context():
        print("Iniciando sincronização automática do Radar...")
        processar_radar_automatico()
        print("Sincronização concluída.")

# --- BLUEPRINTS ---
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Busca a variável 'FLASK_DEBUG', se não existir, assume False (segurança)
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)