# app.py revisado
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

# Configuração do Agendador
class SchedulerConfig:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "America/Sao_Paulo"

app.config.from_object(SchedulerConfig())

# --- INICIALIZAÇÃO ---
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

scheduler = APScheduler()

# Importamos o serviço apenas dentro da função para evitar importação circular no reset_db
def job_automation():
    with app.app_context():
        from services.schedule_service import check_and_post_all_sites
        print(f"--- [SCHEDULER] Verificando sites às {os.popen('date').read().strip()} ---")
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
    t = {
        "hero_title": "Automatize seu Blog",
        "hero_subtitle": "Postagens inteligentes feitas por IA.",
        "hero_button": "TESTAR GRÁTIS",
        "hero_line": "Sua máquina de conteúdo SEO no piloto automático."
    }
    return render_template('landing.html', planos=planos_db, t=t)

# --- INICIALIZAÇÃO SEGURA DO SCHEDULER ---
if __name__ == '__main__':
    # Só inicia o scheduler se não estiver no processo de reloader do Flask
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        scheduler.add_job(id='do_automation', func=job_automation, trigger='interval', minutes=1)
        scheduler.init_app(app)
        scheduler.start()
    
    app.run(host='0.0.0.0', port=5000, debug=True)