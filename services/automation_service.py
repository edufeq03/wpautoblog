def process_pending_posts():
    """
    Esta função seria o seu 'Worker' simplificado.
    Ela busca posts na fila e processa sem travar a UI.
    """
    with app.app_context():
        # Busca apenas 1 post por vez para não sobrecarregar
        task = ContentIdea.query.filter_by(status='pending', is_posted=False).first()
        
        if task:
            print(f">>> [WORKER] Processando post: {task.title}")
            success, message = publish_content_flow(task, task.blog.user)
            # Atualiza o status para não repetir
            task.status = 'completed' if success else 'failed'
            db.session.commit()