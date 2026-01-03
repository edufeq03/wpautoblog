from flask import Flask, render_template
from models import db, login_manager
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from flask_apscheduler import APScheduler
import os
from utils.ai_logic import processar_radar_automatico 

app = Flask(__name__)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'chave-padrao-segura')

# Configuração de banco para suportar PostgreSQL (Easypanel) ou SQLite local
basedir = os.path.abspath(os.path.dirname(__file__))
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or \
    'sqlite:///' + os.path.join(basedir, 'database.db')

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Tenta criar as colunas novas ao iniciar
with app.app_context():
    db.create_all()

scheduler = APScheduler()
app.config['SCHEDULER_API_ENABLED'] = True
scheduler.init_app(app)
scheduler.start()

@scheduler.task('interval', id='sync_radar_job', hours=12)
def scheduled_radar_sync():
    with app.app_context():
        try:
            processar_radar_automatico()
        except Exception as e:
            print(f"Erro no scheduler: {e}")

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)

@app.route('/')
def index():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)