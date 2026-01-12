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
    blog = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
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
        site_id = request.form.get('site_id')
        title = request.form.get('title')
        content = request.form.get('content')
        action = request.form.get('action_type') # 'now' ou 'queue'
        image_file = request.files.get('image_file')

        success, message = content_service.process_manual_post(
            current_user, site_id, title, content, action, image_file
        )
        flash(message, "success" if success else "danger")
        return redirect(url_for('content.ideas'))
    
    return render_template('manual_post.html', blogs=blogs)

def process_manual_post(user, site_id, title, content, action, image_file=None):
    """
    Processa a postagem manual enviada pelo formulário.
    """
    from models import Blog, db
    import services.wordpress_service as wp_service
    import services.image_service as image_service

    blog = Blog.query.filter_by(id=site_id, user_id=user.id).first()
    if not blog:
        return False, "Site não encontrado ou você não tem permissão."

    # Lógica de Imagem
    image_url = None
    if image_file and image_file.filename != '':
        # Se o usuário subiu uma imagem, processamos ela
        image_url = image_service.upload_to_storage(image_file)
    
    # Se for postagem imediata ('now')
    if action == 'now':
        success, msg = wp_service.post_to_wordpress(blog, title, content, image_url)
        if success:
            return True, f"Postagem realizada com sucesso no site {blog.site_name}!"
        else:
            return False, f"Erro ao postar no WordPress: {msg}"
    
    # Se for para a fila ('queue') - Exemplo de implementação simples
    # Aqui você pode salvar em uma tabela de agendamento se tiver uma
    return False, "A função de fila (queue) ainda está em desenvolvimento."

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