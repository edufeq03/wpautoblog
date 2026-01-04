from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_mail import Message
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

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Rota para solicitar a recuperação de senha."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Gera o token de recuperação
            token = user.get_reset_token()
            
            # Constrói a URL de reset
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            try:
                # Importa Mail do app para enviar o email
                from app import mail
                
                msg = Message(
                    subject='Recuperacao de Senha - WP AutoBlog',
                    recipients=[user.email],
                    body=f'''Para recuperar sua senha, clique no link abaixo:
{reset_url}

Este link expira em 30 minutos.

Se voce nao solicitou a recuperacao de senha, ignore este email.'''
                )
                mail.send(msg)
            except Exception as e:
                print(f"Erro ao enviar email: {e}")
                flash('Erro ao enviar email de recuperacao. Tente novamente mais tarde.', 'danger')
                return redirect(url_for('auth.forgot_password'))
        
        # Sempre mostra a mesma mensagem por segurança (não revela se o email existe)
        flash('Se o email existe em nossa base de dados, voce recebera um link de recuperacao.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Rota para resetar a senha usando o token."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))
    
    user = User.verify_reset_token(token)
    if not user:
        flash('Token invalido ou expirado.', 'warning')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        if not password or not password_confirm:
            flash('Preencha todos os campos.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        if password != password_confirm:
            flash('As senhas nao coincidem.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        if len(password) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        try:
            user.password = generate_password_hash(password, method='scrypt')
            db.session.commit()
            flash('Sua senha foi alterada com sucesso! Faca login com a nova senha.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao resetar senha: {e}")
            flash('Erro ao alterar a senha. Tente novamente.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
    
    return render_template('reset_password.html', token=token)

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
