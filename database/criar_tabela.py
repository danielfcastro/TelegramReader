import sqlite3
import os

DB_PATH = 'database/sinais.db'

def criar_banco():
    if not os.path.exists('database'):
        os.makedirs('database')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sinais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            par TEXT,
            tipo_ordem TEXT,
            margem TEXT,
            alavancagem TEXT,
            entry_min REAL,
            entry_max REAL,
            stoploss REAL,
            targets TEXT,
            flag_executado BOOLEAN DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS monitoramentos (
            id SERIAL PRIMARY KEY,
            data_hora TIMESTAMP,
            par TEXT,
            price DOUBLE PRECISION,
            profit INTEGER,
            spent TEXT,
            instruction TEXT,
            target_done TEXT
        );
    ''')
    conn.commit()
    conn.close()
    print("Banco de dados criado ou já existente.")

if __name__ == '__main__':
    criar_banco()