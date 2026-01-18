from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Plan, User, Blog, PostLog
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
@login_required
def ensure_admin():
    """Garante que apenas administradores acessem qualquer rota deste Blueprint."""
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
    
    # Usuários recentes (últimos 7 dias)
    uma_semana_atras = datetime.utcnow() - timedelta(days=7)
    new_users_week = User.query.filter(User.created_at >= uma_semana_atras).count()

    return render_template('admin/dashboard.html', 
                         total_users=total_users, 
                         total_blogs=total_blogs, 
                         posts_today=posts_today,
                         new_users_week=new_users_week)

@admin_bp.route('/plans')
@login_required
def manage_plans():
    """Lista todos os planos para o administrador."""
    plans = Plan.query.order_by(Plan.id.asc()).all()
    return render_template('admin/plans.html', plans=plans)

@admin_bp.route('/edit-plan/<int:id>', methods=['POST'])
@login_required
def edit_plan(id):
    """Atualiza as configurações de um plano específico."""
    plan = Plan.query.get_or_404(id)
    
    try:
        # Campos numéricos e texto
        plan.price = float(request.form.get('price', 0))
        plan.max_sites = int(request.form.get('max_sites', 1))
        plan.posts_per_day = int(request.form.get('posts_per_day', 1))
        plan.credits_monthly = int(request.form.get('credits_monthly', 0))
        
        # Novos campos de exibição e IA
        plan.ia_principal = request.form.get('ia_principal', 'Llama 3 (Quick)')
        plan.support_type = request.form.get('support_type', 'E-mail')
        
        # Tratamento de Checkboxes
        # Se o checkbox for marcado, o navegador envia 'on', senão não envia nada
        plan.permite_img = 'Sim' if request.form.get('permite_img') else 'Não'
        plan.is_public = True if request.form.get('is_public') else False
        
        db.session.commit()
        flash(f"Plano {plan.name} atualizado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao atualizar plano: {str(e)}", "danger")
        
    return redirect(url_for('admin.manage_plans'))

@admin_bp.route('/users')
@login_required
def list_users():
    """Lista todos os usuários e permite alteração de planos."""
    users = User.query.order_by(User.created_at.desc()).all()
    plans = Plan.query.all()
    return render_template('admin/users.html', users=users, plans=plans)

@admin_bp.route('/user/<int:id>/set-plan', methods=['POST'])
@login_required
def set_user_plan(id):
    """Altera o plano de um usuário manualmente."""
    user = User.query.get_or_404(id)
    plan_id = request.form.get('plan_id')
    
    if plan_id:
        try:
            user.plan_id = int(plan_id)
            db.session.commit()
            flash(f"Plano do usuário {user.email} atualizado para {user.plan.name}!", "success")
        except Exception as e:
            db.session.rollback()
            flash("Erro ao atualizar plano do usuário.", "danger")
    
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/user/<int:id>/toggle-admin', methods=['POST'])
@login_required
def toggle_admin(id):
    """Promove ou remove status de administrador de um usuário."""
    user = User.query.get_or_404(id)
    
    # Impede que o admin logado remova a si mesmo acidentalmente
    if user.id == current_user.id:
        flash("Você não pode remover seu próprio acesso administrativo.", "warning")
        return redirect(url_for('admin.list_users'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = "promovido a Admin" if user.is_admin else "removido de Admin"
    flash(f"Usuário {user.email} foi {status}.", "success")
    
    return redirect(url_for('admin.list_users'))