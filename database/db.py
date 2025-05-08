import psycopg2
import logging
from datetime import datetime
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from utils import ajustar_quantidade
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

debug_update=True
debug_select=False
debug_insert=True
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
            if debug_select:
                logger.debug(f"📥 SQL SELECT: {cur.mogrify(query, params).decode()}", )
            cur.execute(query, params)
            resultados = cur.fetchall()
            return resultados

def executar_update(query, params=None):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            if debug_update:
                logger.debug(f"📤 SQL UPDATE: {cur.mogrify(query, params).decode()}")
            cur.execute(query, params)
            conn.commit()

def executar_insert(query, params=None):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            if debug_insert:
                logger.debug(f"➕ SQL INSERT: {cur.mogrify(query, params).decode()}")
            cur.execute(query, params)
            conn.commit()

def conta_sinais_execucao():
    query = """
        SELECT count(*) FROM sinais
        WHERE flag_ordem_enviada = false
    """
    resultado = executar_select(query)
    return resultado[0]["count"] if resultado else 0

#aqui o banco poderia ser atualizado com uma coluna chamada proporção que seria preenchida no momento em que inserir_sinal_com_multiplos_tps for executado.
def buscar_sinal_execucao():
    query = """
        SELECT * FROM sinais
        WHERE flag_ordem_enviada = false and tentativas < 3
        ORDER BY id ASC
    """
    resultado = executar_select(query)
    return resultado if resultado is not None else []

def buscar_sinal_para_be():
    query = """
        SELECT * FROM sinais
        WHERE ativar_be = true AND flag_ordem_enviada = true and tentativas_be <3
        ORDER BY id ASC
        LIMIT 1
    """
    resultado = executar_select(query)
    return resultado if resultado is not None else []

def marcar_ordem_enviada(id_sinal, entry_price, order_id, quantidade):
    query = """
        UPDATE sinais
        SET flag_ordem_enviada = true, entry_price = %(entry_price)s, order_id = %(order_id)s, quantidade = %(quantidade)s
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal, "entry_price": entry_price, "order_id": order_id, "quantidade": quantidade})

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
        SET 
            tentativas_be = tentativas_be + 1,
            ativar_be = CASE 
                WHEN tentativas_be + 1 >= 3 THEN false 
                ELSE ativar_be 
            END
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

def inserir_sinal_com_multiplos_tps(dados, proporcoes):
    agora = datetime.utcnow().isoformat()
    for i in range(1, 5):
        tp_key = f"tp{i}"
        if tp_key in dados and dados[tp_key] is not None:
            novo_sinal = {
                "data_hora": agora,
                "par": dados["pair"],
                "tipo_ordem": dados["type"],
                "margem": dados.get("margin", "Cross"),
                "alavancagem": dados.get("leverage", "20X"),
                "tp": dados[tp_key],
                "sl": dados["stoploss"]
            }

            if i <= len(proporcoes):  # para evitar IndexError
                novo_sinal["proporcao"] = proporcoes[i - 1]

            logger.info(f"📥 Inserindo sinal com TP{i}: {novo_sinal}")
            id_inserido = inserir_sinal(novo_sinal)
            logger.debug(f"🆔 ID gerado para TP{i}: {id_inserido}")
        else:
            logger.warning(f"⚠️ TP{i} não encontrado ou é None")

def inserir_sinal(dados):
    query = """
        INSERT INTO sinais (
            data_hora, par, tipo_ordem, margem, alavancagem,
            tp, sl, proporcao
        ) VALUES (
            %(data_hora)s, %(par)s, %(tipo_ordem)s, %(margem)s, %(alavancagem)s,
            %(tp)s, %(sl)s, %(proporcao)s
        ) RETURNING id
    """
    with conectar_db() as conn:
        with conn.cursor() as cur:
            if debug_insert:
                logger.debug(f"➕ SQL INSERT: {cur.mogrify(query, dados).decode()}")
            cur.execute(query, dados)
            id_gerado = cur.fetchone()[0]
            conn.commit()
            return id_gerado

def buscar_info_apos_sinal_de_monitoramento(par):
    query = """
        SELECT id, order_id, entry_price FROM sinais
        WHERE par = %(par)s AND flag_ordem_enviada = true AND order_id != 0 AND ativar_be = false
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
    SET ativar_be = false
    WHERE par = %(par)s AND 
          flag_ordem_enviada = true
    """
    executar_update(sql, {"par": par})

def atualizar_quantidades(lista_id_quantidade):
    query = """
        UPDATE sinais
        SET quantidade = %(quantidade)s
        WHERE id = %(id)s
    """
    for id_sinal, quantidade in lista_id_quantidade:
        executar_update(query, {"id": id_sinal, "quantidade": quantidade})

def desabilitar_sinal(id_sinal):
    query = """
        UPDATE sinais
        SET tentativas = 3
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

def somar_quantidade_para_be(par):
    sql = """
    SELECT SUM(quantidade) AS total
    FROM sinais
    WHERE par = %(par)s AND ativar_be = true
    """
    resultado = executar_select(sql, {"par": par})
    if resultado and resultado[0]["total"] is not None:
        return resultado[0]["total"]
    return 0.0
