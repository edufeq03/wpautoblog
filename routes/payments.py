from flask import Blueprint, flash, redirect, url_for, request, render_template, jsonify
from flask_login import login_required, current_user
from models import db, User, Plan
import os

payments_bp = Blueprint('payments', __name__)

# Configuração que espelha o marketing e o banco
PLANS_CONFIG = {
    'starter': {
        'nome': 'Starter',
        'preco': '0',
        'sites': 1,
        'posts': 1,
        'credits': 5,
        'interno': False  # Não aparece no pricing interno
    },
    'lite': {
        'nome': 'Lite',
        'preco': '47',
        'sites': 3,
        'posts': 5,
        'credits': 15,
        'interno': True
    },
    'pro': {
        'nome': 'Pro',
        'preco': '97',
        'sites': 5,
        'posts': 10,
        'credits': 30,
        'interno': True
    },
    'vip': {
        'nome': 'VIP',
        'preco': '197',
        'sites': 15,
        'posts': 50,
        'credits': 100,
        'interno': True
    }
}

@payments_bp.route('/pricing')
@login_required
def pricing():
    """
    Exibe a página de preços filtrando apenas os planos para upgrade.
    """
    # Filtra apenas planos marcados como 'interno'
    planos_upgrade = {k: v for k, v in PLANS_CONFIG.items() if v.get('interno')}
    
    # Se você quiser que a Landing Page pegue do banco, 
    # aqui poderíamos fazer: planos_banco = Plan.query.all()
    
    return render_template('pricing.html', planos=planos_upgrade)

@payments_bp.route('/checkout/<string:plano_alvo>')
@login_required
def checkout(plano_alvo):
    """
    Realiza o upgrade de plano associando o ID correto do banco.
    """
    plano_alvo = plano_alvo.lower()
    if plano_alvo not in PLANS_CONFIG:
        flash("Plano selecionado é inválido.", "danger")
        return redirect(url_for('payments.pricing'))

    try:
        # Busca o plano no banco pelo nome capitalizado (Lite, Pro, VIP)
        nome_db = plano_alvo.capitalize()
        novo_plano_db = Plan.query.filter_by(name=nome_db).first()
        
        if not novo_plano_db:
            flash("Erro crítico: Configuração de plano não encontrada no banco.", "danger")
            return redirect(url_for('payments.pricing'))

        # Atualiza o plano e adiciona créditos
        current_user.plan_id = novo_plano_db.id
        creditos_adicionais = PLANS_CONFIG[plano_alvo]['credits']
        current_user.credits += creditos_adicionais
        
        db.session.commit()
        flash(f"🚀 Upgrade concluído! Você agora é {nome_db} e recebeu {creditos_adicionais} créditos.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar upgrade: {str(e)}", "danger")

    return redirect(url_for('dashboard.dashboard_view'))