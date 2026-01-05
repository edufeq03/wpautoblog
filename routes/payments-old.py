from flask import Blueprint, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/upgrade/<string:plano_alvo>')
@login_required
def upgrade_plano(plano_alvo):
    # Dicionário de limites e recompensas
    config_planos = {
        'pro': {'credits': 30, 'label': 'Plano Pro'},
        'vip': {'credits': 100, 'label': 'Plano VIP'}
    }

    if plano_alvo not in config_planos:
        flash("Plano inválido para upgrade.", "danger")
        return redirect(url_for('dashboard.pricing'))

    try:
        # Atualiza o plano e soma os créditos
        current_user.plan_details.name = plano_alvo
        novos_creditos = config_planos[plano_alvo]['credits']
        current_user.credits += novos_creditos
        
        db.session.commit()
        
        flash(f"🎉 Upgrade para {config_planos[plano_alvo]['label']} realizado! +{novos_creditos} créditos adicionados.", "success")
              
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar upgrade: {str(e)}", "danger")

    return redirect(url_for('dashboard.dashboard_view'))