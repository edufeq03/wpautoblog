from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime

sites_bp = Blueprint('sites', __name__)

# --- CONSTANTE PARA O USUÁRIO DEMO ---
DEMO_EMAIL = 'demo@wpautoblog.com.br'

@sites_bp.route('/manage-sites')
@login_required
def manage_sites():
    return render_template('manage_sites.html', user=current_user)

@sites_bp.route('/add-site', methods=['POST'])
@login_required
def add_site():
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Você não pode adicionar novos sites nesta conta.', 'warning')
        return redirect(url_for('sites.manage_sites'))

    if not current_user.can_add_site():
        flash('Limite de sites atingido para o seu plano.', 'error')
        return redirect(url_for('dashboard.pricing'))

    new_blog = Blog(
        user_id=current_user.id,
        site_name=request.form.get('site_name'),
        wp_url=request.form.get('wp_url').strip('/'),
        wp_user=request.form.get('wp_user'),
        wp_app_password=request.form.get('wp_app_password')
    )
    db.session.add(new_blog)
    db.session.commit()
    flash('Site conectado com sucesso!', 'success')
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/delete-site/<int:site_id>', methods=['POST'])
@login_required
def delete_site(site_id):
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Você não pode remover o site de demonstração.', 'danger')
        return redirect(url_for('sites.manage_sites'))

    # 1. Busca o site garantindo que pertence ao usuário
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()

    try:
        # 2. Se você NÃO quiser usar o 'cascade' no models.py, 
        # você teria que deletar os filhos manualmente aqui:
        # PostLog.query.filter_by(blog_id=site_id).delete()
        # ContentIdea.query.filter_by(blog_id=site_id).delete()
        
        # 3. Deleta o site (com o cascade do Passo 1, ele apagará logs e ideias automaticamente)
        db.session.delete(site)
        db.session.commit()
        
        flash(f'O site "{site.site_name}" e todos os dados relacionados foram removidos.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao remover site: {str(e)}', 'danger')
        
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/test-post/<int:site_id>')
@login_required
def test_post(site_id):
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    wp_endpoint = f"{site.wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    
    titulo_teste = "🚀 Teste de Conexão: WP AutoBlog"
    corpo_teste = f"""
    <h2>Conexão Ativa!</h2>
    <p>Este é um post automático de teste para o site <strong>{site.site_name}</strong>.</p>
    <hr>
    <p><small>Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</small></p>
    """

    try:
        response = requests.post(
            wp_endpoint, 
            json={"title": titulo_teste, "content": corpo_teste, "status": "publish"},
            auth=HTTPBasicAuth(site.wp_user, site.wp_app_password), 
            timeout=15
        )
        if response.status_code == 201:
            flash(f"✅ Conexão OK! Post de teste publicado.", "success")
        else:
            flash(f"❌ Erro WP ({response.status_code}). Verifique as credenciais.", "danger")
    except Exception as e:
        flash(f"⚠️ Erro de rede: {str(e)}", "danger")
        
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/update-prompt/<int:site_id>', methods=['POST'])
@login_required
def update_prompt(site_id):
    if current_user.email == DEMO_EMAIL:
        flash('Modo Demo: Alteração desabilitada.', 'warning')
        return redirect(url_for('sites.manage_sites'))

    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    site.master_prompt = request.form.get('master_prompt')
    site.macro_themes = request.form.get('macro_themes') 
    db.session.commit()
    flash('Configurações de IA atualizadas!', 'success')
    return redirect(url_for('sites.manage_sites'))

@sites_bp.route('/update-prefs/<int:site_id>', methods=['POST'])
@login_required
def update_prefs(site_id):
    site = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    site.posts_per_day = request.form.get('posts_per_day', type=int)
    site.schedule_time = request.form.get('schedule_time')
    site.post_status = request.form.get('post_status')
    site.default_category = request.form.get('default_category')

    db.session.commit()
    flash(f"Preferências de {site.site_name} atualizadas!", "success")
    return redirect(url_for('sites.manage_sites'))