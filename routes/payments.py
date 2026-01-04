from flask import Blueprint, flash, redirect, url_for, request, render_template, jsonify
from flask_login import login_required, current_user
from models import db, User
import os
import stripe

payments_bp = Blueprint('payments', __name__)

# Configuração do Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

# Configuração dos Planos
PLANS_CONFIG = {
    'pro': {
        'credits': 30,
        'label': 'Plano Pro',
        'price': 2900,  # Em centavos (R$ 29,00)
        'stripe_price_id': os.environ.get('STRIPE_PRICE_ID_PRO', ''),
    },
    'vip': {
        'credits': 100,
        'label': 'Plano VIP',
        'price': 9900,  # Em centavos (R$ 99,00)
        'stripe_price_id': os.environ.get('STRIPE_PRICE_ID_VIP', ''),
    }
}

@payments_bp.route('/pricing')
def pricing():
    """Exibe a página de preços."""
    return render_template('pricing.html', plans=PLANS_CONFIG)

@payments_bp.route('/upgrade/<string:plano_alvo>')
@login_required
def upgrade_plano(plano_alvo):
    """
    Rota de upgrade de plano (LEGADO - sem pagamento real).
    Mantida para compatibilidade com código antigo.
    """
    if plano_alvo not in PLANS_CONFIG:
        flash("Plano inválido para upgrade.", "danger")
        return redirect(url_for('dashboard.pricing'))

    try:
        config_plano = PLANS_CONFIG[plano_alvo]
        current_user.plan_type = plano_alvo
        
        # Usa o método seguro de dedução de créditos
        if current_user.deduct_credit(-config_plano['credits']):  # Negativo para adicionar
            db.session.commit()
            flash(f"🎉 Upgrade para {config_plano['label']} realizado! +{config_plano['credits']} créditos adicionados.", "success")
        else:
            flash("Erro ao processar upgrade.", "danger")
              
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao processar upgrade: {str(e)}", "danger")

    return redirect(url_for('dashboard.dashboard_view'))

@payments_bp.route('/stripe/create-checkout-session/<string:plano_alvo>', methods=['POST'])
@login_required
def create_checkout_session(plano_alvo):
    """
    Cria uma sessão de checkout do Stripe.
    Retorna o session_id para redirecionar o usuário para o Stripe Checkout.
    """
    if plano_alvo not in PLANS_CONFIG:
        return jsonify({'error': 'Plano inválido'}), 400
    
    if not stripe.api_key:
        return jsonify({'error': 'Stripe não configurado'}), 500
    
    try:
        config_plano = PLANS_CONFIG[plano_alvo]
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'brl',
                    'product_data': {
                        'name': config_plano['label'],
                        'description': f"{config_plano['credits']} créditos",
                    },
                    'unit_amount': config_plano['price'],
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('payments.payment_success', plano_alvo=plano_alvo, _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('payments.payment_cancel', _external=True),
            customer_email=current_user.email,
            metadata={
                'user_id': current_user.id,
                'plano_alvo': plano_alvo,
            }
        )
        
        return jsonify({'sessionId': session.id})
    
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400

@payments_bp.route('/stripe/payment-success')
@login_required
def payment_success():
    """
    Callback de sucesso do Stripe.
    Adiciona créditos ao usuário após confirmação de pagamento.
    """
    session_id = request.args.get('session_id')
    plano_alvo = request.args.get('plano_alvo')
    
    if not session_id or plano_alvo not in PLANS_CONFIG:
        flash('Erro ao processar pagamento.', 'danger')
        return redirect(url_for('dashboard.dashboard_view'))
    
    try:
        # Verifica a sessão no Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        if session.payment_status == 'paid':
            config_plano = PLANS_CONFIG[plano_alvo]
            current_user.plan_type = plano_alvo
            
            # Adiciona créditos usando o método seguro
            current_user.credits += config_plano['credits']
            db.session.commit()
            
            flash(f"✅ Pagamento confirmado! +{config_plano['credits']} créditos adicionados ao seu plano {config_plano['label']}.", "success")
        else:
            flash('Pagamento não confirmado.', 'warning')
    
    except stripe.error.StripeError as e:
        flash(f'Erro ao verificar pagamento: {str(e)}', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar pagamento: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard.dashboard_view'))

@payments_bp.route('/stripe/payment-cancel')
@login_required
def payment_cancel():
    """Callback de cancelamento do Stripe."""
    flash('Pagamento cancelado.', 'info')
    return redirect(url_for('dashboard.dashboard_view'))

@payments_bp.route('/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """
    Webhook do Stripe para processar eventos de pagamento.
    Essencial para confirmar pagamentos de forma segura.
    """
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    
    if not webhook_secret:
        return jsonify({'error': 'Webhook não configurado'}), 400
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return jsonify({'error': 'Payload inválido'}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({'error': 'Assinatura inválida'}), 400
    
    # Processa eventos de pagamento
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        try:
            user_id = session['metadata']['user_id']
            plano_alvo = session['metadata']['plano_alvo']
            
            user = User.query.get(int(user_id))
            if user and plano_alvo in PLANS_CONFIG:
                config_plano = PLANS_CONFIG[plano_alvo]
                user.plan_type = plano_alvo
                user.credits += config_plano['credits']
                db.session.commit()
                print(f"Pagamento confirmado para usuário {user_id}. Créditos adicionados.")
        
        except Exception as e:
            print(f"Erro ao processar webhook: {e}")
            db.session.rollback()
    
    return jsonify({'status': 'success'}), 200

@payments_bp.route('/mercadopago/create-preference/<string:plano_alvo>', methods=['POST'])
@login_required
def create_mercadopago_preference(plano_alvo):
    """
    Cria uma preferência de pagamento no Mercado Pago.
    Retorna o init_point para redirecionar o usuário.
    """
    if plano_alvo not in PLANS_CONFIG:
        return jsonify({'error': 'Plano inválido'}), 400
    
    try:
        import mercadopago
        
        mp = mercadopago.MP(os.environ.get('MERCADOPAGO_ACCESS_TOKEN', ''))
        
        config_plano = PLANS_CONFIG[plano_alvo]
        
        preference = {
            'items': [
                {
                    'title': config_plano['label'],
                    'quantity': 1,
                    'currency_id': 'BRL',
                    'unit_price': config_plano['price'] / 100,  # Converte de centavos para reais
                }
            ],
            'payer': {
                'email': current_user.email,
            },
            'back_urls': {
                'success': url_for('payments.mercadopago_success', plano_alvo=plano_alvo, _external=True),
                'failure': url_for('payments.mercadopago_failure', _external=True),
                'pending': url_for('payments.mercadopago_pending', _external=True),
            },
            'auto_return': 'approved',
            'external_reference': f"user_{current_user.id}_plan_{plano_alvo}",
        }
        
        response = mp.create_preference(preference)
        
        if response['status'] == 201:
            return jsonify({'init_point': response['response']['init_point']})
        else:
            return jsonify({'error': 'Erro ao criar preferência'}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@payments_bp.route('/mercadopago/success')
@login_required
def mercadopago_success():
    """Callback de sucesso do Mercado Pago."""
    plano_alvo = request.args.get('plano_alvo')
    payment_id = request.args.get('payment_id')
    
    if plano_alvo not in PLANS_CONFIG:
        flash('Erro ao processar pagamento.', 'danger')
        return redirect(url_for('dashboard.dashboard_view'))
    
    try:
        import mercadopago
        
        mp = mercadopago.MP(os.environ.get('MERCADOPAGO_ACCESS_TOKEN', ''))
        payment_info = mp.get_payment(payment_id)
        
        if payment_info['response']['status'] == 'approved':
            config_plano = PLANS_CONFIG[plano_alvo]
            current_user.plan_type = plano_alvo
            current_user.credits += config_plano['credits']
            db.session.commit()
            
            flash(f"✅ Pagamento confirmado! +{config_plano['credits']} créditos adicionados ao seu plano {config_plano['label']}.", "success")
        else:
            flash('Pagamento não foi aprovado.', 'warning')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar pagamento: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard.dashboard_view'))

@payments_bp.route('/mercadopago/failure')
@login_required
def mercadopago_failure():
    """Callback de falha do Mercado Pago."""
    flash('Pagamento foi recusado. Tente novamente.', 'danger')
    return redirect(url_for('dashboard.dashboard_view'))

@payments_bp.route('/mercadopago/pending')
@login_required
def mercadopago_pending():
    """Callback de pagamento pendente do Mercado Pago."""
    flash('Seu pagamento está pendente de aprovação.', 'info')
    return redirect(url_for('dashboard.dashboard_view'))
