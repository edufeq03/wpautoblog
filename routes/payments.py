# routes/payments.py
import os
import stripe
from dotenv import load_dotenv
from flask import Blueprint, redirect, url_for, request, render_template, jsonify, current_app
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
            success_url=url_for('payments.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('index', _external=True),
            metadata={
                'user_id': current_user.id,
                'plan_id': plan.id
            }
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        print(f"Erro Stripe: {str(e)}")
        return f"Erro ao criar sessão: {str(e)}", 400
    
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

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        user_id = session['metadata'].get('user_id')
        plan_id = session['metadata'].get('plan_id')

        if user_id and plan_id:
            user = User.query.get(user_id)
            plan = Plan.query.get(plan_id)
            if user and plan:
                # 1. Atualiza o plano do usuário
                user.plan_id = plan.id
                db.session.commit()
                print(f">>> [STRIPE] Plano {plan.name} liberado para {user.email}")
                
                # 2. Adiciona créditos baseados no plano usando o credit_service
                creditos_por_plano = {
                    'Lite': 10,
                    'Pro': 100,
                    'VIP': 500
                }
                quantidade = creditos_por_plano.get(plan.name, 0)
                
                if quantidade > 0:
                    # Chamando a função de serviço para somar créditos com segurança
                    adicionar_creditos(user.id, quantidade) 
                
                # 3. Envia o e-mail de boas-vindas
                send_welcome_email(user.email, plan.name)

    return jsonify({'status': 'success'}), 200