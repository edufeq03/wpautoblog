from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Plan

auth_bp = Blueprint('auth', __name__)

# No auth.py, altere a rota register:
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
            plan_id=free_plan.id if free_plan else None, # Atribui o ID do Free
            credits=5 # Dá os créditos iniciais de presente
            )
        db.session.add(new_user)
        db.session.commit()

        # --- MUDANÇA AQUI: LOGIN AUTOMÁTICO ---
        login_user(new_user)
        
        # Redireciona direto para o hub, que o mandará para o onboarding
        return redirect(url_for('dashboard_hub'))
        
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard.dashboard_view'))
            
        flash('Dados inválidos. Verifique seu e-mail e senha.', 'error')
        
    return render_template('login.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Rota atualizada para enviar e-mail com template HTML profissional."""
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
                
                # Renderiza o template HTML passando a URL de reset
                html_body = render_template('emails/reset_password.html', reset_url=reset_url)
                
                msg = Message(
                    subject='Recuperação de Senha - WP AutoBlog',
                    recipients=[user.email]
                )
                # Fallback em texto simples
                msg.body = f"Para recuperar sua senha, utilize o link: {reset_url}"
                # Conteúdo rico em HTML
                msg.html = html_body
                
                mail.send(msg)
            except Exception as e:
                print(f"Erro ao enviar email: {e}")
                # Log opcional para depuração no servidor
                flash('Ocorreu um problema ao enviar o e-mail. Tente novamente mais tarde.', 'danger')
                return redirect(url_for('auth.forgot_password'))
        
        flash('Se o e-mail informado estiver cadastrado, você receberá instruções de recuperação em instantes.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard_view'))
    
    user = User.verify_reset_token(token)
    if not user:
        flash('O link de recuperação é inválido ou já expirou.', 'warning')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        
        if not password or not password_confirm:
            flash('Por favor, preencha todos os campos.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        if password != password_confirm:
            flash('As senhas digitadas não coincidem.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        if len(password) < 6:
            flash('A senha deve ter no mínimo 6 caracteres.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
        
        try:
            user.password = generate_password_hash(password, method='scrypt')
            db.session.commit()
            flash('Senha atualizada com sucesso! Agora você já pode fazer login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            print(f"Erro ao salvar nova senha: {e}")
            flash('Erro interno ao atualizar a senha.', 'danger')
            return redirect(url_for('auth.reset_password', token=token))
    
    return render_template('reset_password.html', token=token)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sessão encerrada com sucesso.', 'info')
    return redirect(url_for('auth.login'))