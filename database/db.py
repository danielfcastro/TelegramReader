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

#aqui o banco poderia ser atualizado com uma coluna chamada proporção que seria preenchida no momento em que inserir_sinal_com_multiplos_tps for executado.
# Busca de sinais registrados no banco a partir da recepção das mensagens de Telegram
# chamados de TradeExecutor
def buscar_sinal_execucao():
    query = """
        SELECT * FROM sinais
        WHERE ordem_status_id = 0 AND 
              tentativas < 3
        ORDER BY id ASC
    """
    resultado = executar_select(query)
    return resultado if resultado is not None else []

#Usado em TradeExecutor para listar todos os sinais que foram ativados em TelegramReader por ativar_break_even
def buscar_sinal_para_break_even():
    query = """
        SELECT * FROM sinais
        WHERE break_even_status_id = 1 AND 
              ordem_status_id = 1 AND 
              tentativas_be <3
        ORDER BY id ASC
        LIMIT 1
    """
    resultado = executar_select(query)
    return resultado if resultado is not None else []

#Fim da busca de sinais

#Queries de alteração de status
def marcar_ordem_enviada(id_sinal, entry_price, order_id, quantidade):
    query = """
        UPDATE sinais
        SET ordem_status_id = 1, entry_price = %(entry_price)s, order_id = %(order_id)s, quantidade = %(quantidade)s
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal, "entry_price": entry_price, "order_id": order_id, "quantidade": quantidade})

#chamado dentro de TradeExecutor para incrementar o retry de envio de ordem
def incrementar_retry_order(id_sinal):
    query = """
        UPDATE sinais
        SET tentativas = tentativas + 1
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

#chamado dentro de TradeExecutor para incrementar o retry de envio de ordem pra mover SL para Break Even
def incrementar_retry_be(id_sinal):
    query = """
        UPDATE sinais
        SET tentativas_be = tentativas_be + 1
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

#Insere sinal recebido pelo TelegramReader no banco
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
        SELECT * FROM sinais
        WHERE par = %(par)s AND 
              ordem_status_id = 1 AND 
              order_id != 0 AND 
              break_even_status_id = 1
        ORDER BY id DESC
        LIMIT 1
    """
    resultado = executar_select(query, {"par": par})
    return resultado[0] if resultado else None

#Chamado por TelegramReader para marcar o sinal que atingiu TP2 e então ser atualizado por TradeExecutor.py
def ativar_break_even(id_sinal):
    query = """
        UPDATE sinais 
        SET break_even_status_id = 1
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

#Chamado por TradeExecutor após uma execução bem sucedida de broker.ajustar_para_break_even
def marcar_ordem_para_be_executado(par):
    sql = """
    UPDATE sinais
    SET break_even_status_id = 2
    WHERE par = %(par)s AND 
          ordem_status_id = 1
    """
    executar_update(sql, {"par": par})

#chamado quando não encontra o símbolo ao buscar pelo preço
def desabilitar_sinal(id_sinal):
    query = """
        UPDATE sinais
        SET ordem_status_id = 2
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

def somar_quantidade_para_be(par):
    sql = """
    SELECT SUM(quantidade) AS total
    FROM sinais
    WHERE par = %(par)s AND 
          break_even_status_id = 1
    """
    resultado = executar_select(sql, {"par": par})
    if resultado and resultado[0]["total"] is not None:
        return resultado[0]["total"]
    return 0.0