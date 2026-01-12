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
    # Mantém o filtro do site após gerar
    return redirect(url_for('content.ideas', site_id=site_id))

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
    # Carrega os blogs do usuário para o select do formulário
    blogs = Blog.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        site_id = request.form.get('site_id')
        title = request.form.get('title')
        content = request.form.get('content')
        action = request.form.get('action_type') # 'now' ou 'draft'
        
        # IMPORTANTE: Captura o arquivo de imagem usando request.files
        image_file = request.files.get('image')

        # Chama o serviço que processa o upload da imagem e o post no WP
        success, message = content_service.process_manual_post(
            current_user, site_id, title, content, action, image_file
        )
        
        if success:
            flash(message, "success")
            # Redireciona para o relatório de postagens em caso de sucesso
            return redirect(url_for('content.post_report'))
        else:
            flash(message, "danger")
            # Em caso de erro, permanece na página para o usuário revisar os dados
            return render_template('manual_post.html', blogs=blogs)
    
    return render_template('manual_post.html', blogs=blogs)

@content_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed = None
    blogs = Blog.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        url = request.form.get('url') # Corrigido para 'url' conforme o HTML
        processed = content_service.analyze_spy_link(url, getattr(current_user, 'is_demo', False))
        
        if not processed:
            flash("Não foi possível extrair conteúdo deste link. Verifique a URL.", "warning")
            
    return render_template('spy_writer.html', processed_content=processed, blogs=blogs)

@content_bp.route('/post-report')
@login_required
def post_report():
    site_id = request.args.get('site_id', type=int)
    logs = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id).order_by(PostLog.posted_at.desc()).all()
    return render_template('post_report.html', logs=logs)

@content_bp.route('/delete-idea/<int:idea_id>', methods=['POST'])
@login_required
def delete_idea(idea_id):
    if getattr(current_user, 'is_demo', False):
        flash('Modo Demo: Ação bloqueada.', 'warning')
    else:
        idea = ContentIdea.query.get_or_404(idea_id)
        db.session.delete(idea)
        db.session.commit()
        flash('Ideia removida.', 'info')
    return redirect(url_for('content.ideas'))