from flask import Flask, render_template, redirect, url_for, request
from flask_mail import Mail
from models import db, login_manager, Plan
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.payments import payments_bp
from routes.content import content_bp 
from routes.sites import sites_bp 
from routes.radar import radar_bp
from routes.admin import admin_bp
from flask_login import login_required, current_user
from flask_apscheduler import APScheduler
from services.schedule_service import check_and_post_all_sites
import os
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

# Configuração do Agendador (Importante para o fuso horário)
class SchedulerConfig:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "America/Sao_Paulo" # Garante que o relógio interno use o nosso horário

app.config.from_object(SchedulerConfig())

# --- INICIALIZAÇÃO ---
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Inicializa o Scheduler aqui
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# --- DEFINIÇÃO DA TAREFA ---
@scheduler.task('interval', id='do_automation', minutes=1)
def job_automation():
    # Esta mensagem DEVE aparecer no terminal a cada 1 minuto
    print("--- [SCHEDULER] Acordando para verificar sites ---")
    check_and_post_all_sites(app)

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

    # Criamos um objeto 't' de mentira para o HTML não quebrar
    traducoes_fallback = {
        "hero_title": "Automatize seu Blog",
        "hero_subtitle": "Postagens inteligentes feitas por IA.",
        "hero_button": "TESTAR GRÁTIS",
        # adicione outras chaves se o erro persistir em outras linhas
    }

    return render_template('landing.html', planos=planos_db, t=traducoes_fallback)

@app.route('/dashboard-hub')
@login_required
def dashboard_hub():
    status = current_user.get_setup_status()
    return render_template('onboarding.html', status=status)

if __name__ == '__main__':
    # O SEGREDO: use_reloader=False
    # O Flask no modo debug tenta rodar o script duas vezes, o que trava o scheduler.
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)