
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def executar_sql_de_arquivo(cursor, caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        sql = f.read()
        cursor.execute(sql)

def criar_e_popular_banco():
    conn = psycopg2.connect(
        dbname=os.getenv("db_name"),
        user=os.getenv("db_user"),
        password=os.getenv("db_password"),
        host=os.getenv("db_host"),
        port=os.getenv("db_port")
    )
    cursor = conn.cursor()

    print("🛠️ - Criando estrutura de tabelas e populando dados...")

    base_dir = os.path.join(os.path.dirname(__file__), "scripts")
    arquivos_ordem = [
        "break_even_status.sql",
        "ordem_stauts.sql",
        "take_profit_status.sql",
        "sinais.sql",
        "take_profits.sql",
        "inser_break_even_status.sql",
        "inser_ordem_status.sql",
        "inser_take_profit_status.sql"
    ]

    for arquivo in arquivos_ordem:
        caminho_completo = os.path.join(base_dir, arquivo)
        print(f"📄 Executando {arquivo}...")
        executar_sql_de_arquivo(cursor, caminho_completo)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Setup finalizado com sucesso.")

if __name__ == "__main__":
    criar_e_popular_banco()
