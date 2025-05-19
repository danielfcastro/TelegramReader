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
                logger.debug(f"📥 - SQL SELECT: {cur.mogrify(query, params).decode()}", )
            cur.execute(query, params)
            resultados = cur.fetchall()
            return resultados

def executar_update(query, params=None):
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
    global DB_POOL
    if DB_POOL and not DB_POOL.closed:
        DB_POOL.closeall()
        logger.info("✅ - Pool de conexões fechado.")


def atualizar_stop_loss(par, novo_sl):
    """
    Atualiza o Stop Loss da ordem principal de um determinado par.

    Args:
        par (str): Par de trading (ex: "BTC/USDT").
        novo_sl (float): Novo valor de Stop Loss.
    """
    query = """
        UPDATE sinais
        SET sl = %s
        WHERE par = %s AND ordem_status_id = 1
    """
    try:
        executar_update(query, (novo_sl, par))
        logger.info(f"✅ - SL atualizado para {par}: {novo_sl}")
    except Exception as e:
        logger.exception(f"❌ - Falha ao atualizar SL para {par}: {e}")


# Busca de sinais registrados no banco a partir da recepção das mensagens de Telegram
# chamados de TradeExecutor
def sinal_disparar_trade():
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

#Chamado por TelegramReader para marcar o sinal que atingiu TP2 e então ser atualizado por TradeExecutor.py
def sinal_stop_loss_ajuste(id_sinal, sl=None):
    """
    Marca o sinal para ajuste de Stop Loss via TradeExecutor.
    - break_even_status_id = 1 sempre será atualizado.
    - sl só será atualizado se não for None (para evitar violação do NOT NULL).
    """
    if sl is not None:
        query = """
            UPDATE sinais 
            SET break_even_status_id = 1,
                sl = %(sl)s
            WHERE id = %(id)s
        """
        params = {"id": id_sinal, "sl": sl}
    else:
        query = """
            UPDATE sinais 
            SET break_even_status_id = 0
            WHERE id = %(id)s
        """
        params = {"id": id_sinal}

    executar_update(query, params)

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
    WHERE par = %(par)s 
      AND break_even_status_id = 1
      AND ordem_status_id = 1
    """
    resultado = executar_select(sql, {"par": par})
    if resultado and resultado[0]["total"] is not None:
        return resultado[0]["total"]
    return 0.0

def ordem_marcar_concluida(par, tp_numero):
    """
    Marca o TP específico como atingido (tp_status_id = 3) na tabela `take_profits`.

    Se o TP for o último (TP4), também marca a ordem principal como concluída (ordem_status_id = 3)
    na tabela `sinais`.

    Args:
        par (str): Par do sinal, ex: 'BTC/USDT'.
        tp_numero (int): Número do TP atingido (1 a 4).
    """
    # Atualiza o status do TP correspondente
    query_tp = """
        UPDATE take_profits
        SET tp_status_id = 3
        WHERE numero = %(tp_numero)s
          AND sinal_id IN (
              SELECT id FROM sinais
              WHERE par = %(par)s AND ordem_status_id = 1
          )
    """
    executar_update(query_tp, {"par": par, "tp_numero": tp_numero})

    # Se for TP4, marca a ordem como concluída
    if tp_numero == 4:
        query_ordem = """
            UPDATE sinais
            SET ordem_status_id = 3
            WHERE par = %(par)s AND ordem_status_id = 1
        """
        executar_update(query_ordem, {"par": par})


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


#Insere sinal recebido pelo TelegramReader no banco
def ordem_inserir(dados, take_profits):
    """
    Insere um novo sinal na tabela `sinais` e os TPs correspondentes,
    mas sem definir a quantidade dos TPs neste momento.

    Args:
        dados (dict): Dados do sinal (par, tipo_ordem, margem, alavancagem, sl, quantidade, etc.).
        take_profits (list): Lista de dicionários com {numero, valor, proporcao}.

    Returns:
        int: ID do sinal inserido.
    """
    query_sinal = """
        INSERT INTO sinais (
            data_hora, par, tipo_ordem, margem, alavancagem,
            sl, quantidade
        ) VALUES (
            %(data_hora)s, %(par)s, %(tipo_ordem)s, %(margem)s, %(alavancagem)s,
            %(sl)s, %(quantidade)s
        ) RETURNING id
    """

    query_tp = """
        INSERT INTO take_profits (
            sinal_id, numero, valor, proporcao
        ) VALUES (
            %(sinal_id)s, %(numero)s, %(valor)s, %(proporcao)s
        )
    """

    # Insere o sinal e obtém o ID
    sinal_id = executar_insert(query_sinal, dados)

    # Insere os TPs SEM quantidade
    for tp in take_profits:
        tp_dados = {
            "sinal_id": sinal_id,
            "numero": tp["numero"],
            "valor": tp["valor"],
            "proporcao": tp["proporcao"]
        }
        executar_insert(query_tp, tp_dados)

    return sinal_id

def ordem_inserir_tp(sinal_id, take_profits, quantidade_total):
    """
    Insere TPs na tabela `take_profits` com base na quantidade total e proporções.

    Args:
        sinal_id (int): ID do sinal pai.
        take_profits (list): Lista de dicionários com {numero, valor, proporcao}.
        quantidade_total (float): Quantidade total da ordem.
    """
    query = """
        INSERT INTO take_profits (
            sinal_id, numero, valor, quantidade, proporcao
        ) VALUES (
            %(sinal_id)s, %(numero)s, %(valor)s, %(quantidade)s, %(proporcao)s
        )
    """

    for tp in take_profits:
        params = {
            "sinal_id": sinal_id,
            "numero": tp["numero"],
            "valor": tp["valor"],
            "quantidade": round(quantidade_total * tp["proporcao"], 6),
            "proporcao": tp["proporcao"]
        }
        executar_insert(query, params)


def take_profits_por_sinal(sinal_id):
    query = """
        SELECT numero, valor, proporcao FROM take_profits
        WHERE sinal_id = %s
        ORDER BY numero
    """
    return executar_select(query, (sinal_id,))


def ordem_atualizar_tp(sinal_id, numero, quantidade, valor):
    query = """
        UPDATE take_profits
        SET quantidade = %s, valor = %s
        WHERE sinal_id = %s AND numero = %s
    """
    params = (quantidade, valor, sinal_id, numero)
    executar_update(query, params)


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

def atualizar_status_tp(par, numero_tp, novo_status=3):
    """
    Atualiza o status de um Take Profit específico de um par.

    Args:
        par (str): Par do sinal (ex: "BTC/USDT").
        numero_tp (int): Número do TP (1 a 5).
        novo_status (int): Novo status (ex: 3 = atingido).
    """
    query = """
        UPDATE take_profits
        SET tp_status_id = %(status)s
        WHERE sinal_id IN (
            SELECT id FROM sinais
            WHERE par = %(par)s AND ordem_status_id = 1
        )
        AND numero = %(numero)s
    """
    params = {"par": par, "numero": numero_tp, "status": novo_status}
    executar_update(query, params)

def somar_quantidades_tps_ativos(par):
    """
    Soma a quantidade total de TPs com status 2 (AGUARDANDO ENVIO DE SL)
    para sinais com ordem_status_id = 1 (enviada).

    Args:
        par (str): Par de negociação.

    Returns:
        float: Soma total das quantidades.
    """
    query = """
        SELECT SUM(tp.quantidade) AS total
        FROM take_profits tp
        INNER JOIN sinais s ON tp.sinal_id = s.id
        WHERE s.par = %(par)s
          AND s.ordem_status_id = 1
          AND tp.tp_status_id = 2
    """
    resultado = executar_select(query, {"par": par})
    if resultado and resultado[0]["total"] is not None:
        return resultado[0]["total"]
    return 0.0
