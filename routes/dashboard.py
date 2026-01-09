from flask import render_template, request, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, PostLog, Plan  # Adicionado Plan aqui
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def dashboard_view():
    """Página principal do painel com resumo estatístico."""
    # Busca os detalhes do plano através do relacionamento definido no User
    plan = current_user.plan_details
    
    limites = {
        'posts_por_dia': plan.posts_per_day if plan else 1,
        'max_sites': plan.max_sites if plan else 1,
        'nome': plan.name if plan else 'Free'
    }
    
    saldo_atual = current_user.credits if hasattr(current_user, 'credits') else 0
    
    # Busca logs recentes de todos os sites do usuário
    logs_recentes = PostLog.query.join(Blog).filter(Blog.user_id == current_user.id)\
        .order_by(PostLog.posted_at.desc()).limit(5).all()

    # Contagem de posts realizados hoje
    hoje = datetime.utcnow().date()
    posts_hoje = PostLog.query.join(Blog).filter(
        Blog.user_id == current_user.id,
        db.func.date(PostLog.posted_at) == hoje
    ).count()

    return render_template('dashboard.html', 
                           user=current_user, 
                           limite_posts=limites['posts_por_dia'],
                           saldo=saldo_atual, 
                           logs=logs_recentes,
                           posts_hoje=posts_hoje)

@dashboard_bp.route('/pricing')
@login_required
def pricing():
    """Rota de preços que envia a lista de planos para o template."""
    # Busca todos os planos cadastrados no banco de dados
    # Isso envia uma LISTA de objetos, resolvendo o erro do .items()
    planos = Plan.query.order_by(Plan.id.asc()).all()
    
    return render_template('pricing.html', 
                           user=current_user, 
                           planos=planos)