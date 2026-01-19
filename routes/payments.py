# routes/payments.py
import os
import stripe
from dotenv import load_dotenv
from flask import Blueprint, redirect, url_for, request, render_template, jsonify, current_app, flash
from flask_login import login_required, current_user
from flask_mail import Message
from models import db, User, Plan
# Importando as funções do seu novo service
from services.credit_service import adicionar_creditos 

payments_bp = Blueprint('payments', __name__)
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

def send_welcome_email(user_email, plan_name):
    """Envia e-mail de confirmação após o pagamento."""
    try:
        from app import mail 
        
        msg = Message(
            f'¡Bienvenido a EL Postador! 🚀 Plano {plan_name} Ativo',
            recipients=[user_email]
        )
        
        msg.body = f"""
        Olá! 
        
        Seu pagamento foi confirmado com sucesso e seu plano '{plan_name}' já está ativo no EL Postador.
        
        O que você pode fazer agora:
        1. Conectar seu site WordPress no painel.
        2. Configurar seu primeiro Radar de Conteúdo.
        3. Gerar seus primeiros artigos com IA de alta qualidade.
        
        Acesse seu painel aqui: {url_for('dashboard.dashboard_view', _external=True)}
        
        Estamos ansiosos para ver seu conteúdo escalando!
        """
        
        mail.send(msg)
        print(f">>> [E-MAIL] Boas-vindas enviado com sucesso para {user_email}")
    except Exception as e:
        print(f">>> [ERRO E-MAIL] Falha ao enviar para {user_email}: {str(e)}")

 # Rota para pagina de checkout
@payments_bp.route('/checkout/<int:plan_id>')
@login_required
def checkout(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    
    # Mapeamento dinâmico dos IDs do Stripe vindo do .env
    price_map = {
        'Lite': os.getenv('STRIPE_PRICE_ID_LITE'),
        'Pro': os.getenv('STRIPE_PRICE_ID_PRO'),
        'VIP': os.getenv('STRIPE_PRICE_ID_VIP')
    }
    
    stripe_price_id = price_map.get(plan.name)

    if not stripe_price_id:
        flash("Este plano não está disponível para assinatura online.", "warning")
        return redirect(url_for('dashboard.pricing'))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{'price': stripe_price_id, 'quantity': 1}],
            mode='subscription',
            success_url=url_for('payments.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('dashboard.pricing', _external=True),
            metadata={
                'user_id': current_user.id,
                'plan_id': plan.id
            }
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        print(f"Erro Stripe: {e}")
        flash("Erro ao conectar com o meio de pagamento.", "danger")
        return redirect(url_for('dashboard.pricing'))
    
@payments_bp.route('/success')
@login_required
def success():
    return render_template('payments/success.html')

@payments_bp.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    sig_header = request.environ.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session['metadata'].get('user_id')
        plan_id = session['metadata'].get('plan_id')

        if user_id and plan_id:
            with current_app.app_context():
                user = User.query.get(user_id)
                plan = Plan.query.get(plan_id)
                if user and plan:
                    user.plan_id = plan.id
                    # Adiciona os créditos definidos no banco para este plano
                    adicionar_creditos(user.id, plan.credits_monthly)
                    db.session.commit()
                    send_payment_confirmation_email(user.email, plan.name)
    
    return jsonify({'status': 'success'}), 200

def send_payment_confirmation_email(user_email, plan_name):
    mail = current_app.extensions.get('mail')
    if not mail: return
    
    msg = Message(f'Pagamento Confirmado! 🚀 Plano {plan_name} Ativo',
                  recipients=[user_email])
    msg.body = f"Seu plano {plan_name} foi ativado com sucesso. Aproveite as automações!"
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Erro email: {e}")