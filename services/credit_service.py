# services/credit_service.py
from models import db, User

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