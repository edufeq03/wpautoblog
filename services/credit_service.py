# services/credit_service.py
from models import db, User, ApiUsage

def adicionar_creditos(user_id, quantidade):
    """Soma créditos ao saldo do usuário."""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "Usuário não encontrado"
            
        user.credits += quantidade
        db.session.commit()
        print(f">>> [CREDITO] +{quantidade} para {user.name}. Novo saldo: {user.credits}")
        return True, None
    except Exception as e:
        db.session.rollback()
        return False, str(e)

def debitar_creditos(user_id, quantidade):
    """Valida e subtrai créditos do saldo do usuário."""
    try:
        user = User.query.get(user_id)
        if not user:
            return False, "Usuário não encontrado"
            
        if user.credits < quantidade:
            return False, f"Saldo insuficiente. Disponível: {user.credits}"
            
        user.credits -= quantidade
        db.session.commit()
        print(f">>> [DEBITO] -{quantidade} de {user.name}. Restante: {user.credits}")
        return True, None
    except Exception as e:
        db.session.rollback()
        return False, str(e)
    
def log_api_usage(user_id, api_name, feature, tokens=0):
    try:
        usage = ApiUsage(
            user_id=user_id,
            api_name=api_name,
            feature=feature,
            tokens_used=tokens
        )
        db.session.add(usage)
        db.session.commit()
    except Exception as e:
        print(f"Erro ao logar uso de API: {e}")