from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog
from datetime import datetime

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
    """Rota para o cadastro completo via modal único."""
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Ação não permitida.', 'warning')
        return redirect(url_for('sites.manage_sites'))

    # Verifica limite de sites do plano do usuário
    if not current_user.can_add_site():
        flash('Limite de sites atingido para o seu plano.', 'error')
        return redirect(url_for('sites.manage_sites'))

    try:
        # Criando o novo blog com TODOS os campos vindos do modal único
        new_blog = Blog(
            user_id=current_user.id,
            site_name=request.form.get('site_name'),
            wp_url=request.form.get('wp_url', '').strip('/'),
            wp_user=request.form.get('wp_user'),
            wp_app_password=request.form.get('wp_app_password'),
            macro_themes=request.form.get('macro_themes'),
            master_prompt=request.form.get('master_prompt'),
            posts_per_day=int(request.form.get('posts_per_day', 1)),
            schedule_time=request.form.get('schedule_time', '09:00'),
            post_status=request.form.get('post_status', 'publish')
        )
        
        db.session.add(new_blog)
        db.session.commit()
        flash(f'Site "{new_blog.site_name}" conectado e configurado com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cadastrar site: {str(e)}', 'danger')

    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/update-auth/<int:site_id>', methods=['POST'])
@login_required
def update_auth(site_id):
    """Atualiza credenciais de acesso ao WordPress."""
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    
    site.wp_url = request.form.get('wp_url', '').strip('/')
    site.wp_user = request.form.get('wp_user')
    
    # Só atualiza a senha se o usuário preencheu o campo
    new_pwd = request.form.get('wp_app_password')
    if new_pwd and len(new_pwd.strip()) > 0:
        site.wp_app_password = new_pwd

    db.session.commit()
    flash('Conexão WordPress atualizada com sucesso!', 'success')
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/update-prompt/<int:site_id>', methods=['POST'])
@login_required
def update_prompt(site_id):
    """Atualiza a inteligência da IA (Prompt e Temas)."""
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    
    site.macro_themes = request.form.get('macro_themes')
    site.master_prompt = request.form.get('master_prompt')

    db.session.commit()
    flash('Cérebro da IA atualizado!', 'success')
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/update-prefs/<int:site_id>', methods=['POST'])
@login_required
def update_prefs(site_id):
    """Atualiza frequência, horário e status de postagem."""
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    
    try:
        site.posts_per_day = int(request.form.get('posts_per_day', 1))
        site.schedule_time = request.form.get('schedule_time', '09:00')
        site.post_status = request.form.get('post_status', 'publish')

        db.session.commit()
        flash('Configurações de automação salvas!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar preferências: {str(e)}', 'danger')
        
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/delete-site/<int:site_id>', methods=['POST'])
@login_required
def delete_site(site_id):
    """Remove um site e suas configurações."""
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Ação não permitida.', 'warning')
        return redirect(url_for('sites.manage_sites'))

    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    site_name = site.site_name
    
    db.session.delete(site)
    db.session.commit()
    flash(f'O site "{site_name}" foi removido.', 'info')
    return redirect(url_for('sites.manage_sites'))