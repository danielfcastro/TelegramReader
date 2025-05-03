import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os
from dotenv import load_dotenv

load_dotenv()
debug = False
@contextmanager
def conectar_db():
    conn = psycopg2.connect(
        dbname=os.getenv("db_name"),
        user=os.getenv("db_user"),
        password=os.getenv("db_password"),
        host=os.getenv("db_host"),
        port=os.getenv("db_port")
    )
    try:
        yield conn
    finally:
        conn.close()

def executar_select(query, params=None):
    with conectar_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if debug: print("📥 SQL SELECT:", cur.mogrify(query, params).decode())
            cur.execute(query, params)
            resultados = cur.fetchall()
            return resultados

def executar_update(query, params=None):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            print("📤 SQL UPDATE:", cur.mogrify(query, params).decode())
            cur.execute(query, params)
            conn.commit()

def executar_insert(query, params=None):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            print("➕ SQL INSERT:", cur.mogrify(query, params).decode())
            cur.execute(query, params)
            conn.commit()

def conta_sinais_execucao():
    query = """
        SELECT count(*) FROM sinais
        WHERE flag_ordem_enviada = false
    """
    resultado = executar_select(query)
    return resultado[0]["count"] if resultado else 0

def buscar_sinal_execucao():
    query = """
        SELECT * FROM sinais
        WHERE flag_ordem_enviada = false
        ORDER BY id ASC
    """
    resultado = executar_select(query)
    return resultado if resultado is not None else []

def buscar_sinal_para_be():
    query = """
        SELECT * FROM sinais
        WHERE ativar_be = true AND flag_ordem_enviada = true
        ORDER BY id ASC
    """
    resultado = executar_select(query)

def marcar_ordem_enviada(id_sinal, entry_price, order_id):
    query = """
        UPDATE sinais
        SET flag_ordem_enviada = true, entry_price = %(entry_price)s, order_id = %(order_id)s
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal, "entry_price": entry_price, "order_id": order_id})

def incrementar_retry_order(id_sinal):
    query = """
        UPDATE sinais
        SET tentativas = tentativas + 1
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

def incrementar_retry_be(id_sinal):
    query = """
        UPDATE sinais
        SET tentaivas_be = tentaivas_be + 1
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

def desativar_be(id_sinal):
    query = """
        UPDATE sinais
        SET ativar_be = false
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

def inserir_sinal(dados):
    query = """
        INSERT INTO sinais (
            data_hora, par, tipo_ordem, margem, alavancagem,
            entrada_inferior, entrada_superior, tp, sl
        ) VALUES (
            %(data_hora)s, %(par)s, %(tipo_ordem)s, %(margem)s, %(alavancagem)s,
            %(entrada_inferior)s, %(entrada_superior)s, %(tp)s, %(sl)s
        )
    """
    executar_insert(query, dados)

def buscar_info_apos_sinal_de_monitoramento(par):
    query = """
        SELECT id, order_id, entry_price FROM sinais
        WHERE par = %(par)s AND flag_ordem_enviada = true AND order_id != 0
        ORDER BY id DESC
        LIMIT 1
    """
    resultado = executar_select(query, {"par": par})
    return resultado[0] if resultado else None

def ativar_break_even(id_sinal):
    query = """
        UPDATE sinais SET ativar_be = true WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

def marcar_ordem_para_be_executado(par):
    sql = """
    UPDATE sinais
    SET ativar_be = true
    WHERE par = %(par)s AND flag_ordem_enviada = true
    """
    executar_update(sql, {"par": par})