from flask import render_template, request, redirect, url_for, flash, Blueprint, jsonify
from flask_login import login_required, current_user
from models import db, Blog, ContentIdea, PostLog
from services import content_service

content_bp = Blueprint('content', __name__)

# Rota para litar ideias
@content_bp.route('/ideas')
@login_required
def ideas():
    site_id = request.args.get('site_id', type=int)
    ideas_list = content_service.get_filtered_ideas(current_user.id, site_id)
    return render_template('ideas.html', ideas=ideas_list)

# Rota para gerar ideias (botao)
@content_bp.route('/generate-ideas', methods=['POST'])
@login_required
def generate_ideas():
    site_id = request.form.get('site_id')
    if not site_id:
        flash('Por favor, selecione um site para gerar ideias.', 'warning')
        return redirect(url_for('content.ideas'))
        
    blog = Blog.query.filter_by(id=site_id, user_id=current_user.id).first_or_404()
    
    # 1. Executa a lógica no serviço
    count = content_service.generate_ideas_logic(blog)

    # 2. NOVA LÓGICA DE VIGILÂNCIA (Movida para antes do feedback)
    from services.credit_service import log_api_usage
    log_api_usage(current_user.id, "Groq", "Generate Ideas", tokens=500) 
    print(f">>> [VIGILÂNCIA] Consumo registrado para {current_user.email}")
    
    # 3. Feedback para o usuário e Logs do Terminal
    if count > 0:
        flash(f'{count} novas ideias geradas para {blog.site_name}!', 'success')
        print(f">>> [IDEIAS] Usuário {current_user.email} gerou {count} ideias para o blog ID {blog.id}")
    else:
        flash('Não foi possível gerar novas ideias no momento.', 'danger')
        print(f">>> [ERRO] Falha na geração de ideias para {blog.email}")

    # 4. Redirecionamento ÚNICO ao final de tudo
    return redirect(url_for('content.ideas', site_id=site_id))

# Rota para excluir ideias da lista
@content_bp.route('/delete-idea/<int:idea_id>', methods=['POST'])
@login_required
def delete_idea(idea_id):
    if not getattr(current_user, 'is_demo', False):
        idea = ContentIdea.query.get_or_404(idea_id)
        db.session.delete(idea)
        db.session.commit()
        flash('Ideia removida.', 'info')
    return redirect(url_for('content.ideas'))

# Rota para publicar uma ideia no WP
# Consome 1 credito
# Incrementa numero de posts
@content_bp.route('/publish-idea/<int:idea_id>', methods=['POST'])
@login_required
def publish_idea(idea_id):
    # 1. Tenta consumir o crédito primeiro
    # Usamos o método da classe User definido no seu models.py
    if not current_user.consume_credit(1):
        flash("Saldo insuficiente! Cada postagem por IA consome 1 crédito.", "danger")
        return redirect(url_for('content.ideas'))

    # 2. Verifica limites diários do plano
    reached, limit, current = current_user.reached_daily_limit(is_ai_post=True)

    if reached:
        current_user.increase_credit(1) 
        flash(f"Limite diário do plano atingido ({current}/{limit}).", "danger")
        return redirect(url_for('content.ideas'))

    # 3. Busca a ideia e tenta publicar
    idea = ContentIdea.query.get_or_404(idea_id)
    sucesso, msg = content_service.publish_content_flow(idea, current_user)

    if sucesso:
        flash(msg, "success")
    else:
        # LÓGICA DE ESTORNO:
        # Se o fluxo de publicação falhou (erro na OpenAI ou WordPress), devolve o crédito.
        current_user.increase_credit(1)
        flash(f"Falha na publicação: {msg}. Seu crédito foi estornado.", "danger")

    return redirect(url_for('content.ideas'))

# Rota para post manual
# Não consome crédito
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

# Rota para escritor inteligente
# Consome 2 créditos
@content_bp.route('/spy-writer', methods=['GET', 'POST'])
@login_required
def spy_writer():
    processed = None
    blogs = Blog.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        # 1. Verificação de Limite Diário (Antes de cobrar)
        # O Spy Writer é um post de IA, então passamos is_ai_post=True
        reached, limit, current = current_user.reached_daily_limit(is_ai_post=True)
        
        if reached:
            flash(f"Limite diário atingido ({current}/{limit}). Faça upgrade para postar mais.", "warning")
            return render_template('spy_writer.html', processed_content=None, blogs=blogs)

        # 2. Consumo de Créditos (Função avançada: 2 créditos)
        if not current_user.consume_credit(2):
            flash("Créditos insuficientes para usar o Spy Writer. Recarregue seu saldo.", "danger")
            return render_template('spy_writer.html', processed_content=None, blogs=blogs)

        # 3. Execução da Lógica
        url = request.form.get('url')
        try:
            # Chamada ao serviço para extrair e reescrever o conteúdo
            processed = content_service.analyze_spy_link(url, getattr(current_user, 'is_demo', False))
            
            if not processed:
                # Estorno se a extração falhar
                current_user.increase_credit(2)
                flash("Não conseguimos extrair conteúdo desta URL. Verifique o link.", "danger")
            else:
                # Registro de Vigilância de API para o Spy Writer
                from services.credit_service import log_api_usage
                log_api_usage(current_user.id, "Groq/Scraper", "Spy Writer", tokens=1500)
                flash("Conteúdo espiado e reescrito com sucesso!", "success")
                
        except Exception as e:
            current_user.increase_credit(2) # Estorno em caso de erro técnico
            print(f">>> [ERRO SPY] {str(e)}")
            flash("Erro técnico ao processar o Spy Writer. Créditos devolvidos.", "danger")

    return render_template('spy_writer.html', processed_content=processed, blogs=blogs)

# Rota para listar as postagens
@content_bp.route('/post-report')
@login_required
def post_report():
    logs = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id).order_by(PostLog.posted_at.desc()).all()
    return render_template('post_report.html', logs=logs)

@content_bp.route('/consome/<int:quantidade>')
@login_required
def consome_creditos(quantidade):
    # O current_user já é o objeto do usuário logado
    user = current_user 

    # 1. Verificar se o usuário tem créditos suficientes
    if user.credits < quantidade:
        return jsonify({
            "status": "erro", 
            "mensagem": f"Créditos insuficientes. Você tem {user.credits}."
        }), 400

    # 2. Subtrair os créditos
    try:
        user.credits -= quantidade
        db.session.commit() # Salva a alteração no banco de dados
        
        return jsonify({
            "status": "sucesso",
            "mensagem": f"{quantidade} créditos consumidos!",
            "saldo_atual": user.credits
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500
    

@content_bp.route('/aumenta/<int:quantidade>')
@login_required
def aumenta_creditos(quantidade):
    # O current_user já é o objeto do usuário logado
    user = current_user 

    # 1. Incrementa os créditos
    try:
        user.credits += quantidade
        db.session.commit() # Salva a alteração no banco de dados
        
        return jsonify({
            "status": "sucesso",
            "mensagem": f"{quantidade} créditos incrementados!",
            "saldo_atual": user.credits
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "erro", "mensagem": str(e)}), 500