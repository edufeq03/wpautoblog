from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Plan, User, Blog, Plan, PostLog
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
def ensure_admin():
    if not current_user.is_admin:
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for('dashboard.dashboard_view'))

@admin_bp.route('/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('dashboard.dashboard_view'))

    # Estatísticas básicas
    total_users = User.query.count()
    total_blogs = Blog.query.count()
    
    # Posts de hoje
    hoje = datetime.utcnow().date()
    posts_today = PostLog.query.filter(db.func.date(PostLog.posted_at) == hoje).count()
    
    # Novos utilizadores na última semana
    uma_semana_atras = datetime.utcnow() - timedelta(days=7)
    # Nota: Se não tiveres campo 'created_at' no User, esta contagem pode ser adaptada
    new_users_week = 0 
    
    # Cálculo rápido de receita (Soma dos preços dos planos dos utilizadores ativos)
    # Filtramos utilizadores que têm plano (plan_id não é nulo)
    users_with_plans = User.query.filter(User.plan_id.isnot(None)).all()
    revenue = sum([u.plan_details.price for u in users_with_plans if u.plan_details])

    stats = {
        'total_users': total_users,
        'posts_today': posts_today,
        'total_blogs': total_blogs,
        'revenue': f"{revenue:,.2f}",
        'new_users_week': new_users_week
    }

    latest_users = User.query.order_by(User.id.desc()).limit(5).all()

    return render_template('admin/dashboard.html', stats=stats, latest_users=latest_users)

@admin_bp.route('/plans', methods=['GET', 'POST'])
def manage_plans():
    if request.method == 'POST':
        # Lógica para criar novo plano via modal
        new_plan = Plan(
            name=request.form.get('name'),
            max_sites=int(request.form.get('max_sites')),
            posts_per_day=int(request.form.get('posts_per_day')),
            price=float(request.form.get('price'))
        )
        db.session.add(new_plan)
        db.session.commit()
        flash("Plano criado com sucesso!", "success")
        
    plans = Plan.query.order_by(Plan.id.asc()).all()
    return render_template('admin/plans.html', plans=plans)

@admin_bp.route('/plan/edit/<int:id>', methods=['POST'])
def edit_plan(id):
    plan = Plan.query.get_or_404(id)
    plan.price = float(request.form.get('price'))
    plan.posts_per_day = int(request.form.get('posts_per_day'))
    plan.max_sites = int(request.form.get('max_sites'))
    db.session.commit()
    flash(f"Plano {plan.name} atualizado!", "success")
    return redirect(url_for('admin.manage_plans'))

@admin_bp.route('/users')
@login_required
def list_users():
    if not current_user.is_admin:
        return redirect(url_for('dashboard.dashboard_view'))
        
    users = User.query.all()
    plans = Plan.query.all() # Precisamos disto para o modal de edição
    return render_template('admin/users.html', users=users, plans=plans)

@admin_bp.route('/user/<int:id>/set-plan', methods=['POST'])
@login_required
def set_user_plan(id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard.dashboard_view'))
        
    user = User.query.get_or_404(id)
    new_plan_id = request.form.get('plan_id')
    
    user.plan_id = new_plan_id
    db.session.commit()
    
    flash(f"Plano do utilizador {user.email} atualizado com sucesso!", "success")
    return redirect(url_for('admin.list_users'))