import sqlite3
import os

DB_PATH = 'database/sinais.db'

def criar_banco():
    if not os.path.exists('database'):
        os.makedirs('database')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS public.sinais
        (
            id integer NOT NULL DEFAULT nextval('sinais_id_seq'::regclass),
            data_hora text COLLATE pg_catalog."default",
            par text COLLATE pg_catalog."default",
            tipo_ordem text COLLATE pg_catalog."default",
            margem text COLLATE pg_catalog."default",
            alavancagem text COLLATE pg_catalog."default",
            entrada_inferior real,
            entrada_superior real,
            tp1 real,
            tp2 real,
            tp3 real,
            tp4 real,
            stoploss real,
            flag_executado integer DEFAULT 0,
            CONSTRAINT sinais_pkey PRIMARY KEY (id)
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
