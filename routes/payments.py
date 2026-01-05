from flask import Blueprint, flash, redirect, url_for, request, render_template, jsonify
from flask_login import login_required, current_user
from models import db, User, Plan
import os

payments_bp = Blueprint('payments', __name__)

# Configuração Centralizada dos Planos (Preços e Créditos)
PLANS_CONFIG = {
    'free': {
        'id': 1,
        'nome': 'Free',
        'preco': 'R$ 0',
        'sites': 1,
        'posts': 1,
        'credits': 5
    },
    'pro': {
        'id': 2,
        'nome': 'Pro',
        'preco': 'R$ 97',
        'sites': 5,
        'posts': 10,
        'credits': 30
    },
    'vip': {
        'id': 3,
        'nome': 'VIP',
        'preco': 'R$ 197',
        'sites': 15,
        'posts': 50,
        'credits': 100
    }
}

@payments_bp.route('/pricing')
def pricing():
    """Exibe a página de preços enviando a variável 'planos' exigida pelo HTML."""
    return render_template('pricing.html', planos=PLANS_CONFIG)

@payments_bp.route('/checkout/<string:plano_alvo>')
@login_required
def checkout(plano_alvo):
    """
    Simulação de checkout. 
    Por enquanto, realiza o upgrade direto para testes.
    """
    if plano_alvo not in PLANS_CONFIG:
        flash("Plano inválido.", "danger")
        return redirect(url_for('payments.pricing'))

    try:
        # Busca o plano no banco de dados pelo nome
        novo_plano = Plan.query.filter_by(name=plano_alvo.capitalize()).first()
        
        if novo_plano:
            current_user.plan_id = novo_plano.id
            # Adiciona os créditos do pacote
            creditos_pacote = PLANS_CONFIG[plano_alvo]['credits']
            current_user.credits += creditos_pacote
            
            db.session.commit()
            flash(f"🎉 Upgrade para o plano {novo_plano.name} realizado com sucesso! +{creditos_pacote} créditos adicionados.", "success")
        else:
            flash("Erro: Plano não encontrado no banco de dados. Rode o reset_db.py.", "warning")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar upgrade: {str(e)}", "danger")

    return redirect(url_for('dashboard.dashboard_view'))

# ============================================================
# BLOCO DE PAGAMENTOS REAIS (COMENTADO PARA EVITAR ERROS)
# ============================================================
"""
@payments_bp.route('/stripe/create-session/<string:plano_alvo>', methods=['POST'])
@login_required
def create_stripe_session(plano_alvo):
    # Implementar quando tiver as chaves do Stripe em .env
    pass

@payments_bp.route('/mercadopago/create-preference/<string:plano_alvo>', methods=['POST'])
@login_required
def create_mp_preference(plano_alvo):
    # Implementar quando tiver o Access Token do MP
    pass
"""