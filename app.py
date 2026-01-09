# app.py revisado e corrigido
from flask import Flask, render_template, redirect, url_for, request
from models import db, login_manager, Plan, User
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.payments import payments_bp
from routes.content import content_bp 
from routes.sites import sites_bp 
from routes.radar import radar_bp
from routes.admin import admin_bp
from flask_login import login_required, current_user
from flask_apscheduler import APScheduler
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'chave-padrao-segura')
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração do Agendador (Correção de instâncias e Timezone)
class SchedulerConfig:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "America/Sao_Paulo"
    SCHEDULER_JOB_DEFAULTS = {"coalesce": True, "max_instances": 1}

app.config.from_object(SchedulerConfig())

# --- INICIALIZAÇÃO ---
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Inicializa o APScheduler
scheduler = APScheduler()

# Função que será executada pelo agendador
def job_automation():
    with app.app_context():
        from services.schedule_service import check_and_post_all_sites
        # Correção: Usando datetime nativo para não travar o terminal no Windows
        agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        print(f"\n--- [SCHEDULER] Iniciando Verificação: {agora} ---")
        try:
            check_and_post_all_sites(app)
            print(f"--- [SCHEDULER] Verificação Concluída com Sucesso ---")
        except Exception as e:
            print(f"--- [SCHEDULER] Erro Crítico na Automação: {e} ---")

# --- BLUEPRINTS ---
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(sites_bp, url_prefix='/sites')
app.register_blueprint(radar_bp, url_prefix='/radar')
app.register_blueprint(content_bp, url_prefix='/content')
app.register_blueprint(payments_bp, url_prefix='/payments')
app.register_blueprint(admin_bp, url_prefix='/admin')

@app.route('/')
def index():
    planos_db = Plan.query.order_by(Plan.id.asc()).all()
    t = {
        "hero_title": "Automatize seu Blog",
        "hero_subtitle": "Postagens inteligentes feitas por IA.",
        "hero_button": "TESTAR GRÁTIS",
        "hero_line": "Sua máquina de conteúdo SEO no piloto automático."
    }
    return render_template('landing.html', planos=planos_db, t=t)

# --- INICIALIZAÇÃO SEGURA DO SCHEDULER ---
# Fora do main para garantir que o Flask o carregue, 
# mas usamos um try/except para evitar erros em re-execuções
if not scheduler.running:
    scheduler.init_app(app)
    scheduler.start()
    
    # Adiciona o Job para rodar a cada 60 segundos
    try:
        scheduler.add_job(id='job_automation', func=job_automation, trigger='interval', seconds=60)
        print(">>> [SISTEMA] Automação agendada com sucesso (60s).")
    except Exception as e:
        print(f">>> [SISTEMA] Aviso: Job já existe ou falhou ao iniciar: {e}")

if __name__ == '__main__':
    # use_reloader=False é essencial para o Windows não abrir o scheduler 2 vezes!
    app.run(debug=True, port=5000, use_reloader=False)