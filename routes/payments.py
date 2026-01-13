# payments.py corrigido
import os
import stripe
from dotenv import load_dotenv
from flask import Blueprint, redirect, url_for, request, render_template, jsonify
from flask_login import login_required, current_user
from models import db, User, Plan

payments_bp = Blueprint('payments', __name__)

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@payments_bp.route('/checkout/<int:plan_id>')
@login_required
def checkout(plan_id):
    # Usamos plano_id ou plan_id conforme sua rota no landing.html
    plan = Plan.query.get_or_404(plan_id)
    
    # Mapeamento de IDs do Stripe
    stripe_price_id = ""
    if plan.name == 'Lite':
        stripe_price_id = os.getenv('STRIPE_PRICE_ID_LITE')
    elif plan.name == 'Pro':
        stripe_price_id = os.getenv('STRIPE_PRICE_ID_PRO')
    elif plan.name == 'VIP':
        stripe_price_id = os.getenv('STRIPE_PRICE_ID_VIP')

    if not stripe_price_id:
        return f"Erro: Preço para o plano '{plan.name}' não configurado no .env", 400

    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            payment_method_types=['card'],
            line_items=[{
                'price': stripe_price_id,
                'quantity': 1,
            }],
            mode='subscription',
            # _external=True é vital para gerar a URL completa para o Stripe
            success_url=url_for('payments.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('index', _external=True),
            metadata={
                'user_id': current_user.id,
                'plan_id': plan.id
            }
        )
        
        # AQUI ESTÁ A CORREÇÃO: Você deve retornar o redirect para a URL do Stripe
        return redirect(checkout_session.url, code=303)
        
    except Exception as e:
        print(f"Erro Stripe: {str(e)}")
        return f"Erro ao processar pagamento: {str(e)}", 400
    
@payments_bp.route('/success')
@login_required
def success():
    return render_template('payments/success.html')

@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    # Quando o pagamento da assinatura é concluído com sucesso
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Pegamos os dados que enviamos no checkout_session.create
        user_id = session['metadata'].get('user_id')
        plan_id = session['metadata'].get('plan_id')

        if user_id and plan_id:
            user = User.query.get(user_id)
            if user:
                user.plan_id = plan_id
                # Aqui você pode adicionar lógica para somar créditos, se tiver
                db.session.commit()
                print(f">>> [STRIPE] Plano {plan_id} liberado para o usuário {user.email}")

    return jsonify({'status': 'success'}), 200