import sys
import os

# Adiciona a raiz do projeto ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# IMPORTAÇÃO AJUSTADA: Importamos o objeto 'app' diretamente
try:
    from app import app
except ImportError:
    # Se o seu app.py estiver configurado de forma diferente, tentamos uma alternativa comum:
    from main import app 

from models import db, User

def test_fluxo_creditos():
    # Usamos o contexto do seu app existente
    with app.app_context():
        # 1. Busca um usuário de teste
        user = User.query.first()
        if not user:
            print("❌ Erro: Nenhum usuário encontrado no banco para teste.")
            return

        print(f"\n--- Iniciando Teste de Créditos para: {user.email} ---")
        # Forçamos um valor inicial conhecido para o teste não depender do estado atual
        user.credits = 10
        db.session.commit()
        
        print(f"Saldo resetado para o teste: {user.credits}")

        # 2. Teste de Consumo
        print("\nSimulando consumo de 1 crédito...")
        sucesso = user.consume_credit(1)
        if sucesso and user.credits == 9:
            print(f"✅ Consumo OK. Novo saldo: {user.credits}")
        else:
            print(f"❌ Falha no Consumo. Saldo esperado: 9, Saldo real: {user.credits}")

        # 3. Teste de Estorno
        print("\nSimulando estorno de 1 crédito...")
        user.increase_credit(1)
        if user.credits == 10:
            print(f"✅ Estorno OK. Novo saldo: {user.credits}")
        else:
            print(f"❌ Falha no Estorno. Saldo esperado: 10, Saldo real: {user.credits}")

        # 4. Teste de Saldo Insuficiente
        print("\nTestando tentativa de consumo acima do saldo...")
        user.credits = 0
        db.session.commit()
        
        sucesso_negativo = user.consume_credit(1)
        if not sucesso_negativo:
            print("✅ Bloqueio OK: Sistema impediu consumo com saldo zero.")
        else:
            print("❌ ERRO CRÍTICO: Sistema permitiu consumo sem saldo!")

        # Finalização: Limpeza para não deixar o usuário com 0 créditos após o teste
        user.credits = 10
        db.session.commit()
        print("\n--- Testes concluídos com sucesso ---")

if __name__ == "__main__":
    test_fluxo_creditos()