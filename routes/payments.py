from flask import Blueprint, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User
import mercadopago
import os

payments_bp = Blueprint('payments', __name__)

# --- CONFIGURAÇÃO GLOBAL DE PLANOS ---
# Esta é a variável que o seu app.py está procurando
PLANS_CONFIG = {
    1: {"titulo": "Plano Basic", "preco": 47.00, "creditos": 20},
    2: {"titulo": "Plano Pro", "preco": 97.00, "creditos": 50}
}

@payments_bp.route('/webhook/mercadopago', methods=['POST'])
def webhook_mercadopago():
    sdk = mercadopago.SDK(os.environ.get("MP_ACCESS_TOKEN"))
    data = request.get_json()
    
    print(f"DEBUG WEBHOOK RECEBIDO: {data}")

    if data and data.get("type") == "payment":
        payment_id = data.get("data", {}).get("id")
        
        # Consulta os detalhes reais do pagamento
        payment_info = sdk.payment().get(payment_id)
        
        if payment_info["status"] == 200:
            res = payment_info["response"]
            
            # Verificamos se o status é 'approved'
            if res.get("status") == "approved":
                # USAR O ID QUE PASSAMOS NO CHECKOUT
                user_id = res.get("external_reference")
                amount = res.get("transaction_amount")
                
                user = User.query.get(user_id)
                
                if user:
                    print(f"✅ Processando pagamento para o usuário: {user.username}")
                    # Busca a configuração do plano baseada no valor pago
                    for p_id, info in PLANS_CONFIG.items():
                        if amount >= info["preco"]:
                            user.plan_id = p_id
                            user.credits += info["creditos"]
                            break
                    
                    db.session.commit()
                    print(f"💰 Créditos atualizados! Novo saldo de {user.username}: {user.credits}")
                    return jsonify({"status": "success"}), 200
                else:
                    print(f"⚠️ Usuário ID {user_id} não encontrado no banco.")
            else:
                print(f"ℹ️ Pagamento {payment_id} com status: {res.get('status')}")

    return jsonify({"status": "received"}), 200

@payments_bp.route('/buy-credits/<int:plan_id>')
@login_required
def buy_credits(plan_id):
    plan = PLANS_CONFIG.get(plan_id)
    sdk = mercadopago.SDK(os.environ.get("MP_ACCESS_TOKEN"))
    
    preference_data = {
        "items": [
            {
                "title": plan["titulo"],
                "quantity": 1,
                "unit_price": plan["preco"],
                "currency_id": "BRL"
            }
        ],
        "payer": {
            "email": "test_user_123456@testuser.com" # USE UM EMAIL DE TESTE DIFERENTE DO SEU
        },
        "external_reference": str(current_user.id),
        "back_urls": {
            "success": url_for('content.ideas', _external=True),
            "failure": url_for('content.ideas', _external=True)
        },
        "auto_return": "approved",
        "payer": {
            "email": "test_user_123456@testuser.com" 
        },
        # "notification_url": "https://sua-url.ngrok..."  <-- COMENTE ESTA LINHA COM '#'
    }
    
    preference_response = sdk.preference().create(preference_data)
    
    if preference_response["status"] in [200, 201]:
        return redirect(preference_response["response"]["init_point"])
    else:
        print(f"❌ Erro Detalhado: {preference_response['response']}")
        flash("Erro ao iniciar pagamento. Tente novamente em instantes.", "danger")
        return redirect(url_for('content.ideas'))