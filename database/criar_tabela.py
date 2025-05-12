import sqlite3
import os

DB_PATH = 'database/sinais.db'

def criar_banco():
    """
    Cria o banco de dados SQLite com as tabelas `sinais`, `ordem_status` e `break_even_status`.

    Se o diretório `database/` não existir, ele será criado.
    Este script é compatível apenas com SQLite (não usa sintaxe específica do PostgreSQL).

    Tabelas criadas:
        - break_even_status(id, descricao)
        - ordem_status(id, descricao)
        - sinais(..., FOREIGN KEYs para as duas tabelas de status)

    Índices são criados para otimizar consultas por status e tentativas.
    """
    if not os.path.exists('database'):
        os.makedirs('database')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
CREATE TABLE IF NOT EXISTS public.break_even_status
(
    id integer NOT NULL,
    descricao text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT break_even_status_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.break_even_status
    OWNER to tradebot;    
    
CREATE TABLE IF NOT EXISTS public.ordem_status
(
    id integer NOT NULL,
    descricao text COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT trailing_stop_status_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.ordem_status
    OWNER to tradebot;    
    
CREATE TABLE IF NOT EXISTS public.sinais
(
    id integer NOT NULL DEFAULT nextval('sinais_id_seq'::regclass),
    data_hora text COLLATE pg_catalog."default" NOT NULL,
    par text COLLATE pg_catalog."default" NOT NULL,
    tipo_ordem text COLLATE pg_catalog."default" NOT NULL,
    margem text COLLATE pg_catalog."default" NOT NULL,
    alavancagem text COLLATE pg_catalog."default" NOT NULL,
    tp real DEFAULT 0,
    sl real NOT NULL,
    tentativas smallint NOT NULL DEFAULT 0,
    order_id bigint DEFAULT 0,
    entry_price real DEFAULT 0,
    tentativas_be smallint DEFAULT 0,
    quantidade real DEFAULT 0,
    proporcao real NOT NULL DEFAULT 0,
    ordem_status_id smallint NOT NULL DEFAULT 0,
    break_even_status_id smallint NOT NULL DEFAULT 0,
    CONSTRAINT sinais_pkey PRIMARY KEY (id),
    CONSTRAINT fk_break_even_status FOREIGN KEY (break_even_status_id)
        REFERENCES public.break_even_status (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
        NOT VALID,
    CONSTRAINT fk_trailing_stop_status FOREIGN KEY (ordem_status_id)
        REFERENCES public.ordem_status (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
        NOT VALID
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.sinais
    OWNER to tradebot;

CREATE INDEX IF NOT EXISTS fki_fk_break_even_status_id
    ON public.sinais USING btree
    (break_even_status_id ASC NULLS LAST)
    TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_be_ordem_status_tentativas
    ON public.sinais USING btree
    (break_even_status_id ASC NULLS LAST, ordem_status_id ASC NULLS LAST, tentativas_be ASC NULLS LAST)
    TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_ordem_status_tentativas
    ON public.sinais USING btree
    (ordem_status_id ASC NULLS LAST, tentativas ASC NULLS LAST)
    TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_par_break_even_status_id
    ON public.sinais USING btree
    (par COLLATE pg_catalog."default" ASC NULLS LAST, break_even_status_id ASC NULLS LAST)
    TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_par_ordem_orderid_be
    ON public.sinais USING btree
    (par COLLATE pg_catalog."default" ASC NULLS LAST, ordem_status_id ASC NULLS LAST, order_id ASC NULLS LAST, break_even_status_id ASC NULLS LAST)
    TABLESPACE pg_default;

CREATE INDEX IF NOT EXISTS idx_par_ordem_status
    ON public.sinais USING btree
    (par COLLATE pg_catalog."default" ASC NULLS LAST, ordem_status_id ASC NULLS LAST)
    TABLESPACE pg_default;    
    ''')

    conn.commit()
    conn.close()
    print("Banco de dados criado ou já existente.")

if __name__ == '__main__':
    criar_banco()
