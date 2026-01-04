from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Se o usuário já estiver logado, redireciona para o dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'error')
            return redirect(url_for('auth.register'))
            
        # Criando novo usuário com hash de senha seguro
        new_user = User(email=email, password=generate_password_hash(password, method='scrypt'))
        db.session.add(new_user)
        db.session.commit()
        # O PULO DO GATO:
        flash('Conta criada com sucesso! Faça seu login para começar.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Se o usuário já estiver logado, redireciona para o dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        # Verifica se o usuário existe e se a senha está correta
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard.dashboard_view'))
            
        flash('Dados inválidos. Verifique seu e-mail e senha.', 'error')
        
    return render_template('login.html')

@auth_bp.route('/demo-access')
def demo_access():
    """
    Rota para acesso rápido via modo demonstração.
    Efetua login automático com o usuário de teste configurado.
    """
    # Busca o usuário demo criado previamente no banco de dados
    user = User.query.filter_by(email='demo@wpautoblog.com.br').first()
    
    if user:
        login_user(user)
        flash('Bem-vindo à demonstração! Sinta-se à vontade para testar as ferramentas.', 'success')
        return redirect(url_for('dashboard.dashboard_view'))
    
    flash('O modo de demonstração está temporariamente indisponível.', 'danger')
    return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('auth.login'))