# upgrade_database.py
import sqlite3
import os

DB_PATH = 'database/sinais_novo.db'

def criar_novo_banco():
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
            entrada_inferior REAL,
            entrada_superior REAL,
            tp1 REAL,
            tp2 REAL,
            tp3 REAL,
            tp4 REAL,
            stoploss REAL,
            texto_original TEXT,
            flag_executado BOOLEAN DEFAULT 0
        );
    ''')
    conn.commit()
    conn.close()
    print("✅ Nova tabela 'sinais' criada no banco sinais_novo.db.")

if __name__ == '__main__':
    criar_novo_banco()
