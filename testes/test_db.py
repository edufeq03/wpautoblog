import os
from dotenv import load_dotenv
import psycopg2

def test_connection():
    load_dotenv()
    db_url = os.environ.get('DATABASE_URL')
    
    print("--- INICIANDO DIAGNÓSTICO ---")
    if not db_url:
        print("❌ ERRO: DATABASE_URL não encontrada no .env!")
        return

    print(f"📡 Tentando conectar ao host: {db_url.split('@')[-1]}")
    
    try:
        # Tratamento da URL para o psycopg2
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
            
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute('SELECT version();')
        db_version = cur.fetchone()
        print(f"✅ SUCESSO! Conectado ao Postgres.")
        print(f"📦 Versão do Banco: {db_version}")
        
        # Teste de escrita
        cur.execute("SELECT to_regclass('public.users');")
        table_exists = cur.fetchone()[0]
        if table_exists:
            cur.execute("SELECT count(*) FROM users;")
            count = cur.fetchone()[0]
            print(f"👥 Usuários encontrados no banco online: {count}")
        else:
            print("⚠️ Tabelas não encontradas. Você precisa rodar o reset_db.py.")
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ FALHA NA CONEXÃO: {e}")
        print("\nPossíveis causas:")
        print("1. O IP da sua máquina não está autorizado no firewall do Postgres.")
        print("2. A senha no .env contém caracteres especiais não escapados.")
        print("3. O driver psycopg2-binary não está instalado corretamente.")

if __name__ == "__main__":
    test_connection()