import os
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

def criar_banco_postgres():
    """
    Cria as tabelas necessárias no banco PostgreSQL para o sistema de sinais.

    Requer as seguintes variáveis de ambiente (.env):
        - db_name
        - db_user
        - db_password
        - db_host
        - db_port
    """
    conn = psycopg2.connect(
        dbname=os.getenv("db_name"),
        user=os.getenv("db_user"),
        password=os.getenv("db_password"),
        host=os.getenv("db_host"),
        port=os.getenv("db_port")
    )
    cursor = conn.cursor()

    print("✅ Conectado ao PostgreSQL. Criando tabelas...")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS break_even_status (
        id INTEGER PRIMARY KEY,
        descricao TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS ordem_status (
        id INTEGER PRIMARY KEY,
        descricao TEXT NOT NULL
    );

    CREATE SEQUENCE IF NOT EXISTS sinais_id_seq;

    CREATE TABLE IF NOT EXISTS sinais (
        id INTEGER PRIMARY KEY DEFAULT nextval('sinais_id_seq'),
        data_hora TEXT NOT NULL,
        par TEXT NOT NULL,
        tipo_ordem TEXT NOT NULL,
        margem TEXT NOT NULL,
        alavancagem TEXT NOT NULL,
        tp REAL DEFAULT 0,
        sl REAL NOT NULL,
        tentativas SMALLINT NOT NULL DEFAULT 0,
        order_id BIGINT DEFAULT 0,
        entry_price REAL DEFAULT 0,
        tentativas_be SMALLINT DEFAULT 0,
        quantidade REAL DEFAULT 0,
        proporcao REAL NOT NULL DEFAULT 0,
        ordem_status_id SMALLINT NOT NULL DEFAULT 0,
        break_even_status_id SMALLINT NOT NULL DEFAULT 0,
        CONSTRAINT fk_break_even_status FOREIGN KEY (break_even_status_id)
            REFERENCES break_even_status (id),
        CONSTRAINT fk_ordem_status FOREIGN KEY (ordem_status_id)
            REFERENCES ordem_status (id)
    );

    CREATE INDEX IF NOT EXISTS idx_be_ordem_status_tentativas
        ON sinais (break_even_status_id, ordem_status_id, tentativas_be);

    CREATE INDEX IF NOT EXISTS idx_ordem_status_tentativas
        ON sinais (ordem_status_id, tentativas);

    CREATE INDEX IF NOT EXISTS idx_par_break_even_status_id
        ON sinais (par, break_even_status_id);

    CREATE INDEX IF NOT EXISTS idx_par_ordem_orderid_be
        ON sinais (par, ordem_status_id, order_id, break_even_status_id);

    CREATE INDEX IF NOT EXISTS idx_par_ordem_status
        ON sinais (par, ordem_status_id);
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Banco de dados criado ou atualizado com sucesso.")

if __name__ == '__main__':
    criar_banco_postgres()
