import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

# Carrega as variáveis do seu arquivo .env
load_dotenv()

def test_conexao_direta():
    print("--- DEBUG DE CONEXÃO SMTP (EL POSTADOR) ---")
    
    # Pega os dados do seu .env
    smtp_server = os.getenv("MAIL_SERVER")
    smtp_port = int(os.getenv("MAIL_PORT", 587))
    smtp_user = os.getenv("MAIL_USERNAME")
    smtp_pass = os.getenv("MAIL_PASSWORD") # Sua senha de app do Gmail
    
    print(f"Tentando conectar em: {smtp_server}:{smtp_port}")
    print(f"Usuário: {smtp_user}")

    # Cria a mensagem
    msg = EmailMessage()
    msg['Subject'] = "¡Hola! Teste Direto EL Postador"
    msg['From'] = smtp_user
    msg['To'] = smtp_user  # Envia para você mesmo
    msg.set_content("Se você recebeu isso, suas credenciais no .env estão 100% corretas!")

    try:
        # Inicia a conexão
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls() # Inicia criptografia
            print("Criptografia TLS iniciada...")
            
            server.login(smtp_user, smtp_pass)
            print("Login realizado com sucesso!")
            
            server.send_message(msg)
            print("✅ SUCESSO! E-mail enviado com sucesso.")
            
    except Exception as e:
        print(f"❌ ERRO CRÍTICO: {e}")
        print("\nVerificações rápidas:")
        print("1. A senha no .env é a 'Senha de App' de 16 dígitos?")
        print("2. O e-mail no .env está correto?")

if __name__ == "__main__":
    test_conexao_direta()