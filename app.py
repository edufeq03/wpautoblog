from flask import Flask, render_template, redirect, url_for, request
from flask_mail import Mail
from models import db, login_manager
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.payments import payments_bp 
from routes.content import content_bp 
from routes.sites import sites_bp 
from routes.radar import radar_bp # Importe o novo arquivo que criamos
from flask_login import login_required, current_user
import os

app = Flask(__name__)

# Configurações básicas
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'chave-padrao-segura')

# Configuração do Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME')

mail = Mail(app)

# Banco de Dados
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Registro de Blueprints ATIVOS
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(sites_bp, url_prefix='/sites')
app.register_blueprint(radar_bp, url_prefix='/radar')
app.register_blueprint(content_bp, url_prefix='/content')
app.register_blueprint(payments_bp, url_prefix='/billing')

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_hub'))
    return render_template('landing.html')

@app.route('/dashboard-hub')
@login_required
def dashboard_hub():
    status = current_user.get_setup_status()
    finished = request.args.get('finished') == 'true'
    
    # Se o setup estiver completo e não for o momento do "sucesso" (finished=true), vai pro dashboard
    if status == 'complete' and not finished:
        return redirect(url_for('dashboard.dashboard_view'))
    
    return render_template('onboarding.html', status=status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)