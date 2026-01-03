import os
from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, User, Blog 
import requests
from requests.auth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'uma-chave-muito-segura'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:ca60a0635f2a0ba005ab@ep.appmydream.com.br:5435/autoblog_db'

# --- INICIALIZAÇÃO DO BANCO ---
db.init_app(app)

# Configuração do Login
login_manager = LoginManager()
login_manager.login_view = 'login' # Redireciona para aqui se tentar acessar sem login
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- CRIAÇÃO DAS TABELAS ---
with app.app_context():
    # db.drop_all() # Descomente apenas se quiser resetar o banco na VPS
    db.create_all()

# --- ROTAS DE AUTENTICAÇÃO ---

@app.route('/')
@app.route('/vendas')
def landing():
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        print(f"DEBUG: Tentando registrar o email {email}") # <--- ADICIONE ISSO
        password = request.form.get('password')
        
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Este e-mail já está cadastrado.', 'error')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='scrypt')
        new_user = User(email=email, password=hashed_password, plan_type='trial')
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Conta criada com sucesso! Faça login.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Login inválido. Verifique seu e-mail e senha.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('landing'))

# --- ROTAS DO PAINEL (PROTEGIDAS) ---

@app.route('/dashboard')
@login_required # Agora só entra se estiver logado
def dashboard():
    return render_template('dashboard.html', user=current_user, saldo="∞")

@app.route('/manage-sites')
@login_required
def manage_sites():
    return render_template('manage_sites.html', user=current_user)

@app.route('/ideas')
@login_required
def ideas():
    return render_template('ideas.html', user=current_user)

@app.route('/manual-post')
@login_required
def manual_post():
    return render_template('manual_post.html', user=current_user)

@app.route('/post-report')
@login_required
def post_report():
    return render_template('post_report.html', user=current_user)

@app.route('/spy-writer')
@login_required
def spy_writer():
    return render_template('spy_writer.html', user=current_user)

@app.route('/general-config')
@login_required
def general_config():
    return render_template('general_config.html', user=current_user)

@app.route('/pricing')
@login_required
def pricing():
    return render_template('pricing.html', user=current_user)

@app.route('/add-site', methods=['POST'])
@login_required
def add_site():
    # 1. Verificar se o usuário pode adicionar mais sites (Travas de Plano)
    if not current_user.can_add_site():
        flash('Limite de sites atingido para seu plano atual. Faça upgrade para adicionar mais!', 'error')
        return redirect(url_for('pricing'))

    # 2. Coletar dados do formulário
    site_name = request.form.get('site_name')
    wp_url = request.form.get('wp_url').strip('/') # Remove barras extras no final
    wp_user = request.form.get('wp_user')
    wp_app_password = request.form.get('wp_app_password')

    # 3. Criar e salvar o registro
    new_blog = Blog(
        user_id=current_user.id,
        site_name=site_name,
        wp_url=wp_url,
        wp_user=wp_user,
        wp_app_password=wp_app_password
    )
    
    db.session.add(new_blog)
    db.session.commit()
    
    flash(f'Site "{site_name}" conectado com sucesso!', 'success')
    return redirect(url_for('manage_sites'))

@app.route('/test-post/<int:site_id>')
@login_required
def test_post(site_id):
    # 1. Busca o site no banco de dados
    site = Blog.query.get_or_404(site_id)
    
    # Segurança: Verifica se o site pertence ao usuário logado
    if site.user_id != current_user.id:
        flash("Acesso negado!", "error")
        return redirect(url_for('manage_sites'))

    # 2. Dados do post de teste
    wp_endpoint = f"{site.wp_url}/wp-json/wp/v2/posts"
    post_data = {
        "title": "Post de Teste via WP AutoBlog",
        "content": "Parabéns! A conexão entre seu SaaS e o WordPress está funcional. 🚀",
        "status": "publish" 
    }

    try:
        # 3. Tentativa de envio para o WordPress
        response = requests.post(
            wp_endpoint,
            json=post_data,
            auth=HTTPBasicAuth(site.wp_user, site.wp_app_password),
            timeout=10
        )

        if response.status_code == 201:
            flash(f"Sucesso! Post publicado em {site.site_name}", "success")
        else:
            flash(f"Erro no WP: {response.status_code} - Verifique suas Application Passwords.", "error")
            
    except Exception as e:
        flash(f"Erro de conexão: {str(e)}", "error")
    
    return redirect(url_for('manage_sites'))

@app.route('/delete-site/<int:site_id>', methods=['POST'])
@login_required
def delete_site(site_id):
    site = Blog.query.get_or_404(site_id)
    
    # Segurança: garante que o usuário só apague o próprio site
    if site.user_id != current_user.id:
        flash("Acesso negado!", "error")
        return redirect(url_for('manage_sites'))
    
    db.session.delete(site)
    db.session.commit()
    flash(f"Site {site.site_name} removido com sucesso.", "success")
    return redirect(url_for('manage_sites'))

if __name__ == '__main__':
    app.run(debug=True)