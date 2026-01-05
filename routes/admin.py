from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Plan, User

admin_bp = Blueprint('admin', __name__, url_prefix='/super-admin')

@admin_bp.before_request
@login_required
def ensure_admin():
    if not current_user.is_admin:
        flash("Acesso restrito a administradores.", "danger")
        return redirect(url_for('dashboard.dashboard_view'))

@admin_bp.route('/dashboard')
def admin_dashboard():
    stats = {
        'total_users': User.query.count(),
        'total_plans': Plan.query.count()
    }
    return render_template('admin/dashboard.html', stats=stats)

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
        
    plans = Plan.query.all()
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
def set_user_plan(id):
    user = User.query.get_or_404(id)
    user.plan_id = request.form.get('plan_id')
    db.session.commit()
    flash(f"Plano do usuário {user.email} atualizado!", "success")
    return redirect(url_for('admin.list_users'))