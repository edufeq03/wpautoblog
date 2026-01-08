from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea
from services import content_service
from services.scrapers import extrair_texto_da_url # Ponto 3: Movido para services

content_bp = Blueprint('content', __name__)

@content_bp.route('/ideas')
@login_required
def ideas():
    site_id = request.args.get('site_id', type=int)
    ideas_list = content_service.get_filtered_ideas(current_user.id, site_id)
    return render_template('ideas.html', ideas=ideas_list)

@content_bp.route('/generate-ideas', methods=['POST'])
@login_required
def generate_ideas():
    blog = Blog.query.filter_by(id=request.form.get('site_id'), user_id=current_user.id).first_or_404()
    count = content_service.generate_ideas_logic(blog)
    flash(f'{count} ideias geradas para {blog.site_name}!', 'success')
    return redirect(url_for('content.ideas'))

@content_bp.route('/publish-idea/<int:idea_id>', methods=['POST'])
@login_required
def publish_idea(idea_id):
    idea = ContentIdea.query.get_or_404(idea_id)
    sucesso, msg = content_service.publish_content_flow(idea, current_user)
    flash(msg, "success" if sucesso else "danger")
    return redirect(url_for('content.ideas'))

@content_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    blogs = Blog.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        # Lógica de post manual simplificada
        flash("Funcionalidade em manutenção para novos padrões.", "info")
    return render_template('manual_post.html', blogs=blogs)

@content_bp.route('/post-report')
@login_required
def post_report():
    site_id = request.args.get('site_id', type=int)
    logs = content_service.get_post_reports(current_user.id, site_id)
    return render_template('post_report.html', logs=logs)

@content_bp.route('/delete-idea/<int:idea_id>', methods=['POST'])
@login_required
def delete_idea(idea_id):
    if getattr(current_user, 'is_demo', False):
        flash('Modo Demo: Remoção desabilitada.', 'warning')
        return redirect(url_for('content.ideas'))
    idea = ContentIdea.query.get_or_404(idea_id)
    db.session.delete(idea)
    db.session.commit()
    return redirect(url_for('content.ideas'))

@content_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed = None
    if request.method == 'POST':
        url = request.form.get('wp_url')
        raw_text = extrair_texto_da_url(url)
        processed = content_service.generate_text(f"Reescreva: {raw_text[:2000]}") if raw_text else None
    return render_template('spy_writer.html', processed_content=processed)