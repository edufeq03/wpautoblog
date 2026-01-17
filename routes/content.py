from flask import render_template, request, redirect, url_for, flash, Blueprint, jsonify
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea, PostLog
from services import content_service

content_bp = Blueprint('content', __name__)

# Rota para listar ideias
@content_bp.route('/ideas')
@login_required
def ideas():
    site_id = request.args.get('site_id', type=int)
    ideas_list = content_service.get_filtered_ideas(current_user.id, site_id)
    return render_template('ideas.html', ideas=ideas_list)

# Rota para gerar ideias via IA (Groq)
@content_bp.route('/generate-ideas', methods=['POST'])
@login_required
def generate_ideas():
    site_id = request.form.get('site_id')
    print(f"DEBUG: Gerando ideias para o site_id: {site_id}")
    
    if not site_id:
        flash('Por favor, selecione um site para gerar ideias.', 'warning')
        return redirect(url_for('content.ideas'))
        
    blog = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    
    # Executa a lógica de geração de títulos/insights
    count = content_service.generate_ideas_logic(blog)

    # Registro de consumo de API para controle financeiro
    from services.credit_service import log_api_usage
    log_api_usage(current_user.id, "Groq", "Generate Ideas", tokens=500) 
    
    if count > 0:
        flash(f'{count} novas ideias geradas para {blog.site_name}!', 'success')
    else:
        flash('Não foi possível gerar novas ideias no momento.', 'danger')

    return redirect(url_for('content.ideas', site_id=site_id))

# Rota para excluir ideias
@content_bp.route('/delete-idea/<int:idea_id>', methods=['POST'])
@login_required
def delete_idea(idea_id):
    if not getattr(current_user, 'is_demo', False):
        idea = ContentIdea.query.get_or_404(idea_id)
        db.session.delete(idea)
        db.session.commit()
        flash('Ideia removida.', 'info')
    return redirect(url_for('content.ideas'))

# PUBLICAÇÃO VIA FILA (Otimizado para o Scheduler)
@content_bp.route('/publish-idea/<int:idea_id>', methods=['POST'])
@login_required
def publish_idea(idea_id):
    # 1. Validação de Créditos
    if not current_user.consume_credit(1):
        flash("Saldo insuficiente! Recarregue seus créditos.", "danger")
        return redirect(url_for('content.ideas'))

    # 2. Validação de Limites do Plano
    reached, limit, current = current_user.reached_daily_limit(is_ai_post=True)
    if reached:
        current_user.increase_credit(1) # Estorno imediato
        flash(f"Limite diário atingido ({current}/{limit}).", "danger")
        return redirect(url_for('content.ideas'))

    # 3. Envio para a Fila
    idea = ContentIdea.query.get_or_404(idea_id)
    idea.status = 'pending'
    db.session.commit()

    flash(f"O post '{idea.title}' foi enviado para processamento e aparecerá no blog em instantes.", "success")
    return redirect(url_for('content.ideas'))

# POST MANUAL (Opção de Fila ou Imediato)
@content_bp.route('/manual-post', methods=['GET', 'POST'])
@login_required
def manual_post():
    blogs = Blog.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        site_id = request.form.get('site_id')
        title = request.form.get('title')
        content = request.form.get('content')
        action = request.form.get('action_type') # 'queue' ou 'now'
        image_file = request.files.get('image')

        # Se o usuário optar por usar a fila do Worker
        if action == 'queue':
            nova_ideia = ContentIdea(
                blog_id=site_id,
                title=title,
                content_insight=content,
                status='pending',
                is_posted=False
            )
            db.session.add(nova_ideia)
            db.session.commit()
            flash("Post manual adicionado à fila de processamento.", "success")
            return redirect(url_for('content.post_report'))

        # Publicação imediata (Síncrona)
        success, message = content_service.process_manual_post(
            current_user, site_id, title, content, action, image_file
        )
        if success:
            flash(message, "success")
            return redirect(url_for('content.post_report'))
        flash(message, "danger")
        
    return render_template('manual_post.html', blogs=blogs)

# SPY WRITER (IA + Fila)
@content_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed = None
    blogs = Blog.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        # Ação após a reescrita: Enviar o texto pronto para a fila do WordPress
        if request.form.get('action_type') == 'enqueue_spy':
            site_id = request.form.get('site_id')
            title = request.form.get('title')
            content = request.form.get('content')
            
            nova_ideia = ContentIdea(
                blog_id=site_id,
                title=title,
                content_insight=content,
                status='pending'
            )
            db.session.add(nova_ideia)
            db.session.commit()
            flash("Conteúdo reescrito enviado para a fila com sucesso!", "success")
            return redirect(url_for('dashboard.home'))

        # Lógica de "Espionagem" (Extração e reescrita inicial)
        reached, _, _ = current_user.reached_daily_limit(is_ai_post=True)
        if reached:
            flash("Limite diário atingido.", "warning")
            return render_template('spy_writer.html', processed_content=None, blogs=blogs)

        if not current_user.consume_credit(2):
            flash("Créditos insuficientes.", "danger")
            return render_template('spy_writer.html', processed_content=None, blogs=blogs)

        url = request.form.get('url')
        try:
            processed = content_service.analyze_spy_link(url, getattr(current_user, 'is_demo', False))
            if processed:
                from services.credit_service import log_api_usage
                log_api_usage(current_user.id, "Groq/Scraper", "Spy Writer", tokens=1500)
                flash("Conteúdo processado! Você pode editar abaixo ou enviar direto para a fila.", "success")
            else:
                current_user.increase_credit(2)
                flash("Não foi possível extrair dados desta URL.", "danger")
        except Exception as e:
            current_user.increase_credit(2)
            flash(f"Erro no processamento: {str(e)}", "danger")

    return render_template('spy_writer.html', processed_content=processed, blogs=blogs)

# Relatório de Postagens
@content_bp.route('/post-report')
@login_required
def post_report():
    logs = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id).order_by(PostLog.posted_at.desc()).all()
    return render_template('post_report.html', logs=logs)

# Rotas de utilidade para créditos (API interna)
@content_bp.route('/consome/<int:quantidade>')
@login_required
def consome_creditos(quantidade):
    if current_user.consume_credit(quantidade):
        return jsonify({"status": "sucesso", "saldo_atual": current_user.credits}), 200
    return jsonify({"status": "erro", "mensagem": "Saldo insuficiente"}), 400

@content_bp.route('/aumenta/<int:quantidade>')
@login_required
def aumenta_creditos(quantidade):
    current_user.increase_credit(quantidade)
    return jsonify({"status": "sucesso", "saldo_atual": current_user.credits}), 200