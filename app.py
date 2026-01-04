from flask import Flask, render_template, redirect, url_for, request
from models import db, login_manager
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.payments import payments_bp 
from routes.content import content_bp 
from routes.sites import sites_bp 
from routes.radar import radar_bp 
from flask_apscheduler import APScheduler
from flask_login import login_required, current_user # Importado para o funcionamento do hub
from werkzeug.security import generate_password_hash
import os
from utils.ai_logic import processar_radar_automatico 

app = Flask(__name__)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'chave-padrao-segura')

# Configuração de banco
basedir = os.path.abspath(os.path.dirname(__file__))
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or \
    'sqlite:///' + os.path.join(basedir, 'database.db')

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Registro de Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(sites_bp, url_prefix='/sites')
app.register_blueprint(content_bp, url_prefix='/content')
app.register_blueprint(radar_bp, url_prefix='/radar')
app.register_blueprint(payments_bp, url_prefix='/billing')

# --- ROTAS DE FLUXO PRINCIPAL ---

@app.route('/')
def index():
    # Se logado, manda para o hub decidir se vai para onboarding ou dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_hub'))
    return render_template('landing.html')

@app.route('/dashboard-hub')
@login_required
def dashboard_hub():
    status = current_user.get_setup_status()
    
    # Se o usuário acabou de completar o setup, mas queremos que ele veja a página de onboarding
    # adicionamos um parâmetro 'finished=true' na URL
    finished = request.args.get('finished') == 'true'
    
    if status == 'complete' and not finished:
        return redirect(url_for('dashboard.dashboard_view'))
    
    # Se o status for incompleto OU se ele acabou de terminar (finished=true), mostra onboarding
    return render_template('onboarding.html', status=status)

# --- CONFIGURAÇÕES DE SCHEDULER E DEMO ---

def garantir_usuario_demo():
    from models import User, Blog
    demo_email = 'demo@wpautoblog.com.br'
    if not User.query.filter_by(email=demo_email).first():
        novo_demo = User(
            email=demo_email,
            password=generate_password_hash('demo123', method='pbkdf2:sha256'),
            plan_type='vip',
            credits=100
        )
        db.session.add(novo_demo)
        db.session.commit()
        
        site_teste = Blog(
            user_id=novo_demo.id,
            site_name="Blog de Teste Demo",
            wp_url="https://wp.appmydream.com.br",
            wp_user="Maria",
            wp_app_password="qw5Z b2K3 NcIt oHkT nmg4 bpAe",
            macro_themes="Tecnologia, Marketing Digital, IA"
        )
        db.session.add(site_teste)
        db.session.commit()

with app.app_context():
    db.create_all()
    garantir_usuario_demo()

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

if __name__ == '__main__':
    # 3. Inicialização completa do servidor
    app.run(
        host='0.0.0.0', # Permite acesso externo (essencial para Docker/Easypanel)
        port=5000,      # Porta padrão (pode alterar para 80 ou 8080 se precisar)
        debug=True      # Ativa o Auto-reload e o depurador interativo no navegador
    )