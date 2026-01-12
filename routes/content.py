from flask import render_template, request, redirect, url_for, flash, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea, PostLog
from services import content_service

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
    site_id = request.form.get('site_id')
    if not site_id:
        flash('Por favor, selecione um site para gerar ideias.', 'warning')
        return redirect(url_for('content.ideas'))
        
    blog = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    count = content_service.generate_ideas_logic(blog)
    
    flash(f'{count} novas ideias geradas para {blog.site_name}!', 'success')
    return redirect(url_for('content.ideas', site_id=site_id))

@content_bp.route('/publish-idea/<int:idea_id>', methods=['POST'])
@login_required
def publish_idea(idea_id):
    # Regra 1: Post de IA consome crédito
    if not current_user.consume_credit(1):
        flash("Saldo insuficiente! Cada postagem por IA consome 1 crédito.", "danger")
        return redirect(url_for('content.ideas'))

    # Trava de limite diário (mantida como segunda camada de segurança)
    reached, limit, current = content_service.user_reached_limit(current_user, is_ai_post=True)
    if reached:
        flash(f"Limite diário do plano atingido.", "danger")
        return redirect(url_for('content.ideas'))

    idea = ContentIdea.query.get_or_404(idea_id)
    # Passando o current_user para o serviço
    sucesso, msg = content_service.publish_content_flow(idea, current_user)
    flash(msg, "success" if sucesso else "danger")
    return redirect(url_for('content.ideas'))

@content_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    blogs = Blog.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        # Post manual não chama a trava 'reached', permitindo uso livre
        site_id = request.form.get('site_id')
        title = request.form.get('title')
        content = request.form.get('content')
        action = request.form.get('action_type')
        image_file = request.files.get('image')

        success, message = content_service.process_manual_post(
            current_user, site_id, title, content, action, image_file
        )
        if success:
            flash(message, "success")
            return redirect(url_for('content.post_report'))
        flash(message, "danger")
    return render_template('manual_post.html', blogs=blogs)

@content_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed = None
    blogs = Blog.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        # Regra 2: Spy Writer consome crédito (ex: 2 créditos por ser uma função avançada)
        if current_user.consume_credit(2):
            url = request.form.get('url')
            processed = content_service.analyze_spy_link(url, getattr(current_user, 'is_demo', False))
        else:
            flash("Créditos insuficientes para usar o Spy Writer.", "danger")
    return render_template('spy_writer.html', processed_content=processed, blogs=blogs)

@content_bp.route('/post-report')
@login_required
def post_report():
    logs = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id).order_by(PostLog.posted_at.desc()).all()
    return render_template('post_report.html', logs=logs)

@content_bp.route('/delete-idea/<int:idea_id>', methods=['POST'])
@login_required
def delete_idea(idea_id):
    if not getattr(current_user, 'is_demo', False):
        idea = ContentIdea.query.get_or_404(idea_id)
        db.session.delete(idea)
        db.session.commit()
        flash('Ideia removida.', 'info')
    return redirect(url_for('content.ideas'))