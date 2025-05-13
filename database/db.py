import logging
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

load_dotenv()
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

debug_update=True
debug_select=False
debug_insert=True

# Inicializa o pool globalmente
DB_POOL = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
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
    Context manager que cria e fecha uma conexão com o banco de dados PostgreSQL.

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
                logger.debug(f"📥 SQL SELECT: {cur.mogrify(query, params).decode()}", )
            cur.execute(query, params)
            resultados = cur.fetchall()
            return resultados

def executar_update(query, params=None):
    """
    Executa uma instrução UPDATE no banco.

    Args:
        query (str): SQL com placeholders.
        params (dict, optional): Parâmetros da consulta.
    """
    with conectar_db() as conn:
        with conn.cursor() as cur:
            if debug_update:
                logger.debug(f"📤 SQL UPDATE: {cur.mogrify(query, params).decode()}")
            cur.execute(query, params)
            conn.commit()

def executar_insert(query, params=None):
    """
    Executa uma instrução INSERT no banco.

    Args:
        query (str): SQL com placeholders.
        params (dict, optional): Parâmetros da consulta.
    """
    with conectar_db() as conn:
        with conn.cursor() as cur:
            if debug_insert:
                logger.debug(f"➕ SQL INSERT: {cur.mogrify(query, params).decode()}")
            cur.execute(query, params)
            conn.commit()

def fechar_pool():
    if DB_POOL:
        DB_POOL.closeall()
        logger.info("✅ - Pool de conexões fechado.")

# Busca de sinais registrados no banco a partir da recepção das mensagens de Telegram
# chamados de TradeExecutor
def sinal_disparar_trade():
    """
    Busca sinais pendentes de execução com menos de 3 tentativas.
    ordem_status_id = 0 - RECEBIDA
    Returns:
        list[dict]: Lista de sinais prontos para envio de ordem.
    """
    query = """
        SELECT * FROM sinais
        WHERE ordem_status_id = 0 AND 
              tentativas < 3
        ORDER BY id ASC
    """
    resultado = executar_select(query)
    return resultado if resultado is not None else []

#Chamado por TelegramReader para marcar o sinal que atingiu TP2 e então ser atualizado por TradeExecutor.py
def break_even_ativado(id_sinal):
    """
    Ativa o status de break-even para o sinal informado.
    break_even_status_id = 1 - ATIVAR
    Args:
        id_sinal (int): ID do sinal.
    """
    query = """
        UPDATE sinais 
        SET break_even_status_id = 1
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

#Chamado por TradeExecutor após uma execução bem sucedida de broker.ajustar_para_break_even
def break_even_configurado(par):
    """
    Marca o sinal como tendo o break-even executado com sucesso.
    ordem_status_id = 1 - ENVIADA
    break_even_status_id = 2 - CONFIGURADO
    Args:
        par (str): Par da ordem.
    """
    sql = """
    UPDATE sinais
    SET break_even_status_id = 2
    WHERE par = %(par)s AND 
          ordem_status_id = 1
    """
    executar_update(sql, {"par": par})

def break_even_desativado(id_sinal):
    """
    Desativa o status de break-even para o sinal informado.
    break_even_status_id = 0 - ATIVAR
    Args:
        id_sinal (int): ID do sinal.
    """
    query = """
        UPDATE sinais 
        SET break_even_status_id = 0
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

#chamado dentro de TradeExecutor para incrementar o retry de envio de ordem pra mover SL para Break Even
def break_even_incrementar_retry(id_sinal):
    """
    Incrementa a contagem de tentativas de ajuste de break-even.

    Args:
        id_sinal (int): ID do sinal.
    """
    query = """
        UPDATE sinais
        SET tentativas_be = tentativas_be + 1
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

#Usado em TradeExecutor para listar todos os sinais que foram ativados em TelegramReader por ativar_break_even
def break_even_sinal():
    """
    Busca o próximo sinal apto a ter break-even ativado.
    break_even_status_id = 1 - ATIVAR
    ordem_status_id = 1 - ENVIADA
    Returns:
        list[dict]: Lista com no máximo 1 sinal pronto para ajuste de BE.
    """
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

def break_even_soma_quantidade(par):
    """
    Soma a quantidade total de sinais com break-even pendente para o par.
    break_even_status_id = 1 - ATIVAR
    Args:
        par (str): Par a ser analisado.

    Returns:
        float: Soma das quantidades.
    """
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

#chamado quando não encontra o símbolo ao buscar pelo preço
def ordem_desabilitar(id_sinal):
    """
    Desabilita um sinal definindo status como falha (ordem_status_id = 2).
    ordem_status_id = 2 - DESABILITADA
    Args:
        id_sinal (int): ID do sinal a ser desabilitado.
    """
    query = """
        UPDATE sinais
        SET ordem_status_id = 2
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

def ordem_info(par):
    """
    Busca o último sinal válido para break-even de um determinado par.
    ordem_status_id = 1 - ENVIADA
    break_even_status_id = 0 - INATIVO
    Args:
        par (str): Par de negociação, ex: 'BTC/USDT'.

    Returns:
        dict | None: Registro mais recente se existir, ou None.
    """
    query = """
        SELECT * FROM sinais
        WHERE par = %(par)s AND 
              ordem_status_id = 1 AND 
              order_id != 0 AND 
              break_even_status_id = 0 AND
              tentativas_be < 3
        ORDER BY id DESC
        LIMIT 1
    """
    resultado = executar_select(query, {"par": par})
    return resultado[0] if resultado else None

#Insere sinal recebido pelo TelegramReader no banco
def ordem_inserir(dados):
    """
    Insere um novo sinal na tabela `sinais`.
    ordem_status_id = 0 - RECEBIDA - DEFAULT
    break_even_status_id = 0 - INATIVO - DEFAULT
    Args:
        dados (dict): Campos obrigatórios como par, tipo_ordem, margem, alavancagem, etc.

    Returns:
        int: ID do sinal recém-inserido.
    """
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

#chamado dentro de TradeExecutor para incrementar o retry de envio de ordem
def ordem_incrementar_retry(id_sinal):
    """
    Incrementa a contagem de tentativas de envio de ordem.

    Args:
        id_sinal (int): ID do sinal.
    """
    query = """
        UPDATE sinais
        SET tentativas = tentativas + 1
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal})

#Queries de alteração de status
def ordem_enviada(id_sinal, entry_price, order_id, quantidade):
    """
    Marca um sinal como executado com ordem enviada com sucesso.
    ordem_status_id = 1 - ENVIADA
    Args:
        id_sinal (int): ID do sinal.
        entry_price (float): Preço de entrada.
        order_id (int): ID da ordem na corretora.
        quantidade (float): Quantidade negociada.
    """
    query = """
        UPDATE sinais
        SET ordem_status_id = 1, 
            entry_price = %(entry_price)s, 
            order_id = %(order_id)s, 
            quantidade = %(quantidade)s
        WHERE id = %(id)s
    """
    executar_update(query, {"id": id_sinal, "entry_price": entry_price, "order_id": order_id, "quantidade": quantidade})