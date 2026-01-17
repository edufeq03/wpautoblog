from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Plan, User, Blog, PostLog
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
    # Estatísticas básicas
    total_users = User.query.count()
    total_blogs = Blog.query.count()
    
    # Posts de hoje
    hoje = datetime.utcnow().date()
    posts_today = PostLog.query.filter(db.func.date(PostLog.posted_at) == hoje).count()
    
    # Novos utilizadores na última semana (se houver campo created_at)
    new_users_week = 0 

    # Se você não for admin, bloqueie o acesso (recomendado)
    if not current_user.is_admin: # Ajuste conforme seu campo de admin
        return redirect(url_for('content.brainstorm'))
    # 1. Calculando as estatísticas para o template
    uma_semana_atras = datetime.utcnow() - timedelta(days=7)
    
    stats = {
        'total_users': User.query.count(),
        'new_users_week': User.query.filter(User.created_at >= uma_semana_atras).count(),
        'total_blogs': Blog.query.count(),
        'total_posts': PostLog.query.count()
    }
    
    return render_template('admin/dashboard.html', 
                         total_users=total_users, 
                         total_blogs=total_blogs, 
                         stats=stats,
                         posts_today=posts_today,
                         current_user=current_user)

@admin_bp.route('/plans', methods=['GET', 'POST'])
@login_required
def manage_plans():
    if request.method == 'POST':
        # Criação de novo plano (caso use esta função)
        new_plan = Plan(
            name=request.form.get('name'),
            price=float(request.form.get('price')),
            posts_per_day=int(request.form.get('posts_per_day')),
            max_sites=int(request.form.get('max_sites')),
            has_images=True if request.form.get('has_images') else False
        )
        db.session.add(new_plan)
        db.session.commit()
        flash("Plano criado com sucesso!", "success")
        
    # Busca os planos ordenados pelo ID para manter a ordem consistente
    plans = Plan.query.order_by(Plan.id.asc()).all()
    return render_template('admin/plans.html', plans=plans)

@admin_bp.route('/plan/edit/<int:id>', methods=['POST'])
@login_required
def edit_plan(id):
    plan = Plan.query.get_or_404(id)
    
    # Atualização dos campos
    plan.price = float(request.form.get('price'))
    plan.posts_per_day = int(request.form.get('posts_per_day'))
    plan.max_sites = int(request.form.get('max_sites'))
    
    # Lógica para o checkbox de imagens
    plan.has_images = True if request.form.get('has_images') else False
    
    try:
        db.session.commit()
        flash(f"Plano {plan.name} atualizado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao atualizar plano: {str(e)}", "danger")
        
    return redirect(url_for('admin.manage_plans'))

@admin_bp.route('/users')
@login_required
def list_users():
    users = User.query.all()
    plans = Plan.query.all()
    return render_template('admin/users.html', users=users, plans=plans)

@admin_bp.route('/user/<int:id>/set-plan', methods=['POST'])
@login_required
def set_user_plan(id):
    user = User.query.get_or_404(id)
    plan_id = request.form.get('plan_id')
    
    if plan_id:
        user.plan_id = int(plan_id)
        db.session.commit()
        flash(f"Plano do usuário {user.email} atualizado!", "success")
    
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/user/<int:id>/toggle-admin', methods=['POST'])
@login_required
def toggle_admin(id):
    user = User.query.get_or_404(id)
    # Evita que o admin atual remova seu próprio acesso por erro
    if user.id == current_user.id:
        flash("Você não pode remover seu próprio acesso administrativo.", "warning")
    else:
        user.is_admin = not user.is_admin
        db.session.commit()
        status = "adicionado como Admin" if user.is_admin else "removido como Admin"
        flash(f"Usuário {user.email} {status}.", "info")
    
    return redirect(url_for('admin.list_users'))