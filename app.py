from flask import Flask, render_template
from models import db, login_manager
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.payments import payments_bp # Importe o novo arquivo
from flask_apscheduler import APScheduler
from werkzeug.security import generate_password_hash
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

def garantir_usuario_demo():
    """Cria o usuário demo caso ele não exista no banco de dados."""
    from models import User, Blog  # Import local para evitar importação circular
    
    demo_email = 'demo@wpautoblog.com.br'
    user_demo = User.query.filter_by(email=demo_email).first()

    if not user_demo:
        print(">>> Criando usuário demo pela primeira vez...")
        # Cria o usuário com plano VIP para a demonstração ser completa
        novo_demo = User(
            email=demo_email,
            password=generate_password_hash('demo123', method='pbkdf2:sha256'),
            plan_type='vip',
            credits=100  # Saldo generoso para a demo
        )
        db.session.add(novo_demo)
        db.session.commit()
        
        # Opcional: Já conectar um site de teste ao demo
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
        print(">>> Usuário demo e site de teste criados com sucesso.")
    else:
        print(">>> Usuário demo já existe.")

# Tenta criar as colunas novas ao iniciar
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

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(payments_bp) # Registre o blueprint

@app.route('/')
def index():
    return render_template('landing.html')

# Tarefa para resetar contadores diários (se você salvar posts_hoje no banco)
# Se você calcula os posts_hoje por consulta (como está no dashboard.py), 
# o reset é "automático" porque a data muda.
@scheduler.task('cron', id='reset_daily_limits', hour=0, minute=1)
def reset_daily_limits():
    with app.app_context():
        # Se você tiver uma coluna 'posts_realizados_hoje' no User:
        # User.query.update({User.posts_hoje: 0})
        # db.session.commit()
        print("Fim do dia: Contadores virtuais resetados pela mudança de data.")

if __name__ == '__main__':
    with app.app_context():
        # 1. Garante que as tabelas existam
        db.create_all()
        
        # 2. Executa a lógica de semente (Cria o usuário demo se não existir)
        from werkzeug.security import generate_password_hash
        from models import User
        
        demo_email = 'demo@wpautoblog.com.br'
        if not User.query.filter_by(email=demo_email).first():
            print(">>> Criando ambiente de demonstração...")
            demo_user = User(
                email=demo_email,
                password=generate_password_hash('demo123'),
                plan_type='vip',
                credits=100
            )
            db.session.add(demo_user)
            db.session.commit()
            print(">>> Usuário demo pronto!")

    # 3. Inicialização completa do servidor
    app.run(
        host='0.0.0.0', # Permite acesso externo (essencial para Docker/Easypanel)
        port=5000,      # Porta padrão (pode alterar para 80 ou 8080 se precisar)
        debug=True      # Ativa o Auto-reload e o depurador interativo no navegador
    )