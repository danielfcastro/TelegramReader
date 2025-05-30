import logging
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError

load_dotenv()
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

debug_update=True
debug_select=False
debug_insert=True

# Inicializa o pool globalmente
DB_POOL = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=3,
    dbname=os.getenv("db_name"),
    user=os.getenv("db_user"),
    password=os.getenv("db_password"),
    host=os.getenv("db_host"),
    port=os.getenv("db_port")
)

if not DB_POOL:
    raise Exception("❌ - Falha ao inicializar pool de conexões com o banco.")

@contextmanager
def conectar_db():
    """
    Context manager que gerencia a conexão com o banco de dados PostgreSQL.

    Garante que a conexão seja retornada ao pool, mesmo em caso de erro.

    Yields:
        connection (psycopg2.extensions.connection): Conexão ativa com o banco.
    """
    conn = DB_POOL.getconn()
    try:
        yield conn
    finally:
        # Só tenta devolver a conexão se ela foi obtida e o pool está ativo
        if conn and not DB_POOL.closed:
            DB_POOL.putconn(conn)

def executar_select(query, params=None):
    """
    Executa uma consulta SELECT no banco e retorna os resultados como dicionários.

    Args:
        query (str): Comando SQL.
        params (dict, optional): Parâmetros para interpolar na query.

    Returns:
        list[dict]: Lista de resultados.
    """
    with conectar_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if debug_select:
                logger.debug(f"📥 - SQL SELECT: {cur.mogrify(query, params).decode()}", )
            cur.execute(query, params)
            resultados = cur.fetchall()
            return resultados

def executar_update(query, params=None):
    """
    Executa uma instrução UPDATE no banco.

    Args:
        query (str): Comando SQL.
        params (dict, optional): Parâmetros da query.

    Observação:
        Em caso de falha de conexão, tenta uma nova conexão automaticamente.
    """
    try:
        with conectar_db() as conn:
            with conn.cursor() as cur:
                if debug_update:
                    logger.debug(f"📤 - SQL UPDATE: {cur.mogrify(query, params).decode()}")
                cur.execute(query, params)
                conn.commit()
    except OperationalError as e:
        logger.warning("⚠️ - Conexão perdida com o banco. Tentando nova conexão...")
        DB_POOL.putconn(conn, close=True)  # fecha a antiga
        conn = DB_POOL.getconn()
        with conn.cursor() as cur:
            cur.execute(query, params)
            conn.commit()

def executar_insert(query, params=None):
    """
    Executa uma instrução INSERT no banco e retorna o ID gerado, se aplicável.

    Args:
        query (str): SQL com placeholders.
        params (dict, optional): Parâmetros da consulta.

    Returns:
        Any: Valor retornado (ex: ID gerado), ou None se não houver RETURNING.
    """
    with conectar_db() as conn:
        with conn.cursor() as cur:
            if debug_insert:
                logger.debug(f"➕ - SQL INSERT: {cur.mogrify(query, params).decode()}")
            cur.execute(query, params)
            retorno = None
            if cur.description:  # Isso indica que há RETURNING na query
                retorno = cur.fetchone()[0]
            conn.commit()
            return retorno

def fechar_pool():
    """
    Fecha a conexão com o banco de dados PostgreSQL.
    """
    global DB_POOL
    if DB_POOL and not DB_POOL.closed:
        DB_POOL.closeall()
        logger.info("✅ - Pool de conexões fechado.")


#MÉTODOS DE DISPARO DE TRADE
# Busca de sinais registrados no banco a partir da recepção das mensagens de Telegram
# chamados de TradeExecutor
def trade_fire():
    """
    Busca sinais pendentes de execução
    ordem_status_id = 0 - RECEBIDA
    Returns:
        list[dict]: Lista de sinais prontos para envio de ordem.
    """
    query = """
        SELECT * FROM sinais
        WHERE ordem_status_id = 0
        ORDER BY id DESC
        FOR UPDATE SKIP LOCKED
    """
    resultado = executar_select(query)
    return resultado if resultado is not None else []


def ordem_info(par, exigir_break_even_inativo=False):
    """
    Busca a última ordem enviada para um determinado par.

    Se `exigir_break_even_inativo` for True, filtra apenas ordens com break_even_status_id = 0.

    Args:
        par (str): Par de negociação, ex: 'BTC/USDT'.
        exigir_break_even_inativo (bool): Se True, filtra por break_even_status_id = 0.

    Returns:
        dict | None: Registro mais recente da ordem, ou None.
    """
    condicoes = [
        "par = %(par)s",
        "ordem_status_id = 1",
        "order_id != 0"
    ]

    if exigir_break_even_inativo:
        condicoes.append("break_even_status_id = 0")

    query = f"""
        SELECT * FROM sinais
        WHERE {' AND '.join(condicoes)}
        ORDER BY id DESC
        LIMIT 1
    """
    resultado = executar_select(query, {"par": par})
    return resultado[0] if resultado else None