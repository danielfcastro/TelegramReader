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
            order_id bigint DEFAULT 0,
            data_hora text COLLATE pg_catalog."default",
            par text COLLATE pg_catalog."default",
            tipo_ordem text COLLATE pg_catalog."default",
            margem text COLLATE pg_catalog."default",
            alavancagem text COLLATE pg_catalog."default",
            entrada_inferior real DEFAULT 0,
            entrada_superior real DEFAULT 0,
            entry_price real DEFAULT 0,
            tp real DEFAULT 0,
            sl real DEFAULT 0,
            flag_ordem_enviada boolean DEFAULT false,
            retry_order_send smallint DEFAULT 0,
            retry_be_send smallint DEFAULT 0,
            ativar_be boolean DEFAULT false
            CONSTRAINT sinais_pkey PRIMARY KEY (id)
        );
                   
        CREATE INDEX IF NOT EXISTS idx_sinais_tentativas_sl
            ON public.sinais USING btree
            (tentativas_sl ASC NULLS LAST)
            WITH (deduplicate_items=True)
            TABLESPACE pg_default;                                                          
    ''')
    conn.commit()
    conn.close()
    print("Banco de dados criado ou já existente.")

if __name__ == '__main__':
    criar_banco()
