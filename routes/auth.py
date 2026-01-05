from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Plan

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('E-mail já cadastrado.', 'error')
            return redirect(url_for('auth.register'))
            
        free_plan = Plan.query.filter_by(name='Free').first()
        new_user = User(
            email=email, 
            password=generate_password_hash(password, method='scrypt'),
            plan_id=free_plan.id if free_plan else None,
            credits=5
            )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('dashboard.dashboard_view')) # Ajustado para sua rota de dashboard
        
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.admin_dashboard'))
        return redirect(url_for('dashboard.dashboard_view'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False # Captura o 'lembrar-me'
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user, remember=remember)
            
            # 1. Prioridade: Se o usuário tentou acessar uma página restrita antes (parâmetro next)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
                
            # 2. Redirecionamento baseado no cargo (Admin vs Cliente)
            if hasattr(user, 'is_admin') and user.is_admin:
                return redirect(url_for('admin.admin_dashboard'))
            
            return redirect(url_for('dashboard.dashboard_view'))
            
        flash('Dados inválidos. Verifique seu e-mail e senha.', 'error')
        
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sessão encerrada com sucesso.', 'info')
    # Redireciona para a Landing Page (ajuste 'main.index' para o nome da sua rota inicial)
    return redirect(url_for('auth.logout')) 

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            token = user.get_reset_token()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            try:
                from app import mail
                html_body = render_template('emails/reset_password.html', reset_url=reset_url)
                
                msg = Message(
                    subject='Recuperação de Senha - WP AutoBlog',
                    recipients=[user.email]
                )
                msg.body = f"Para recuperar sua senha, utilize o link: {reset_url}"
                msg.html = html_body
                mail.send(msg)
            except Exception as e:
                print(f"Erro ao enviar email: {e}")
                flash('Erro ao enviar o e-mail. Tente novamente mais tarde.', 'danger')
                return redirect(url_for('auth.forgot_password'))
        
        flash('Se o e-mail estiver cadastrado, você receberá instruções em instantes.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))
    
    user = User.verify_reset_token(token)
    if not user:
        flash('Link inválido ou expirado.', 'warning')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        if password != password_confirm:
            flash('As senhas não coincidem.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        if len(password) < 6:
            flash('Mínimo de 6 caracteres.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        user.password = generate_password_hash(password, method='scrypt')
        db.session.commit()
        flash('Senha atualizada!', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html', token=token)