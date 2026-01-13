# app.py revisado e completo - EL POSTADOR
from flask import Flask, render_template, redirect, url_for, request
from models import db, login_manager, Plan, User
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.payments import payments_bp
from routes.content import content_bp 
from routes.sites import sites_bp 
from routes.radar import radar_bp
from routes.admin import admin_bp
from routes.teste import teste_bp
from flask_login import login_required, current_user
from flask_mail import Mail
from flask_apscheduler import APScheduler
import os
from datetime import datetime
from dotenv import load_dotenv

# 1. Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÕES DE BANCO DE DADOS ---
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- CONFIGURAÇÕES DE E-MAIL (SMTP GMAIL) ---
# Aqui estava o erro: as chaves precisam estar no app.config
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

# --- INICIALIZAÇÃO DE EXTENSÕES ---
db.init_app(app)
login_manager.init_app(app)
mail = Mail(app) # Agora o mail lerá as configurações acima corretamente
scheduler = APScheduler()

# --- REGISTRO DE BLUEPRINTS ---
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(sites_bp, url_prefix='/sites')
app.register_blueprint(radar_bp, url_prefix='/radar')
app.register_blueprint(content_bp, url_prefix='/content')
app.register_blueprint(payments_bp, url_prefix='/payments')
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(teste_bp, url_prefix='/teste')

@app.route('/')
def index():
    planos_db = Plan.query.order_by(Plan.id.asc()).all()
    return render_template('landing.html', planos=planos_db)

# --- CONFIGURAÇÃO DO SCHEDULER (AUTOMAÇÃO) ---
def job_automation():
    with app.app_context():
        # Aqui entra a lógica de verificação de posts agendados
        pass

if not scheduler.running:
    scheduler.init_app(app)
    scheduler.start()
    try:
        # Verifica a cada 60 segundos
        scheduler.add_job(id='job_automation', func=job_automation, trigger='interval', seconds=60)
        print(">>> [SISTEMA] EL Postador: Automação agendada (60s).")
    except Exception as e:
        print(f">>> [ERRO SCHEDULER] {e}")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)