from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog
from datetime import datetime
from services.wordpress_service import test_wp_connection

sites_bp = Blueprint('sites', __name__)

# --- CONSTANTE PARA O USUÁRIO DEMO ---
DEMO_EMAIL = 'demo@wpautoblog.com.br'

@sites_bp.route('/manage-sites')
@login_required
def manage_sites():
    """Lista todos os sites do usuário logado."""
    user_sites = Blog.query.filter_by(user_id=current_user.id).all()
    return render_template('manage_sites.html', sites=user_sites)

@sites_bp.route('/add-site', methods=['POST'])
@login_required
def add_site():
    """Rota para o cadastro completo com validação de saúde do WordPress."""
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Ação não permitida.', 'warning')
        return redirect(url_for('sites.manage_sites'))

    # 1. Verifica limite de sites do plano do usuário
    if not current_user.can_add_site():
        flash('Limite de sites atingido para o seu plano.', 'danger')
        return redirect(url_for('sites.manage_sites'))

    # 2. Coleta dados do formulário
    wp_url = request.form.get('wp_url').strip().rstrip('/')
    wp_user = request.form.get('wp_user').strip()
    wp_app_password = request.form.get('wp_app_password').strip()

    # 3. VALIDAÇÃO SDD: Testar conexão antes de salvar
    is_valid, message = test_wp_connection(wp_url, wp_user, wp_app_password)
    
    if not is_valid:
        flash(f"Falha na conexão WordPress: {message}", 'danger')
        return redirect(url_for('sites.manage_sites'))

    try:
        # 4. Criando o novo blog após validação de sucesso
        new_blog = Blog(
            user_id=current_user.id,
            site_name=request.form.get('site_name'),
            wp_url=wp_url,
            wp_user=wp_user,
            wp_app_password=wp_app_password,
            ai_prompt=request.form.get('ai_prompt'),
            macro_themes=request.form.get('macro_themes'),
            posts_per_day=int(request.form.get('posts_per_day', 1)),
            schedule_time=request.form.get('schedule_time', '09:00'),
            post_status=request.form.get('post_status', 'publish'),
            timezone=request.form.get('timezone', 'UTC')
        )
        db.session.add(new_blog)
        db.session.commit()
        flash('Site conectado e validado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro interno ao salvar site: {str(e)}', 'danger')
        
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/update-auth/<int:site_id>', methods=['POST'])
@login_required
def update_auth(site_id):
    """Atualiza e re-valida as credenciais de um site existente."""
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Ação não permitida.', 'warning')
        return redirect(url_for('sites.manage_sites'))

    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    
    new_url = request.form.get('wp_url').strip().rstrip('/')
    new_user = request.form.get('wp_user').strip()
    new_pass = request.form.get('wp_app_password').strip()

    # Validação antes de atualizar
    is_valid, message = test_wp_connection(new_url, new_user, new_pass)
    
    if is_valid:
        site.wp_url = new_url
        site.wp_user = new_user
        site.wp_app_password = new_pass
        db.session.commit()
        flash('Credenciais atualizadas e validadas!', 'success')
    else:
        flash(f'As novas credenciais são inválidas: {message}', 'danger')
        
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/update-prompt/<int:site_id>', methods=['POST'])
@login_required
def update_prompt(site_id):
    """Atualiza apenas a inteligência do site."""
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    site.ai_prompt = request.form.get('ai_prompt')
    site.macro_themes = request.form.get('macro_themes')
    db.session.commit()
    flash('Inteligência do site atualizada!', 'success')
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/update-prefs/<int:site_id>', methods=['POST'])
@login_required
def update_prefs(site_id):
    """Atualiza preferências de postagem."""
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    
    try:
        site.posts_per_day = int(request.form.get('posts_per_day', 1))
        site.schedule_time = request.form.get('schedule_time', '09:00')
        site.post_status = request.form.get('post_status', 'publish')
        site.timezone = request.form.get('timezone', 'America/Sao_Paulo')

        db.session.commit()
        flash('Configurações de automação salvas!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar preferências: {str(e)}', 'danger')
        
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/delete-site/<int:site_id>', methods=['POST'])
@login_required
def delete_site(site_id):
    """Remove um site."""
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Ação não permitida.', 'warning')
        return redirect(url_for('sites.manage_sites'))

    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    db.session.delete(site)
    db.session.commit()
    flash('Site removido com sucesso.', 'info')
    return redirect(url_for('sites.manage_sites'))