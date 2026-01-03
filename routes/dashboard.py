from flask import render_template, request, Blueprint
from flask_login import login_required, current_user
from models import db, Blog, PostLog
from datetime import datetime

dashboard_bp = Blueprint('dashboard', __name__)

# --- CONFIGURAÇÃO DE PLANOS (Pode ser movido para um arquivo de config futuro) ---
PLANOS = {
    'trial': {'nome': 'Plano Trial', 'preco': 'Grátis', 'sites': '1', 'posts': '1', 'espiao': False},
    'pro': {'nome': 'Plano Pro', 'preco': 'R$ 59', 'sites': '2', 'posts': '5', 'espiao': True},
    'vip': {'nome': 'Plano VIP', 'preco': 'R$ 249', 'sites': 'Ilimitados', 'posts': 'Ilimitadas', 'espiao': True}
}

@dashboard_bp.route('/dashboard')
@login_required
def dashboard_view():
    """Página principal do painel com resumo estatístico."""
    limites = current_user.get_plan_limits()
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
    """Página de listagem de planos e upgrades."""
    return render_template('pricing.html', user=current_user, planos=PLANOS)

@dashboard_bp.route('/general-config')
@login_required
def general_config():
    """Configurações gerais da conta do usuário."""
    return render_template('general_config.html', user=current_user)