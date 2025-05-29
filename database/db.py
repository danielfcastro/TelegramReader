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
debug_insert=False

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


#MÉTODOS DE SINAIS - STOP LOSS
def stop_loss_update(symbol, novo_sl):
    """
    Atualiza o Stop Loss da ordem principal de um determinado symbol.

    Args:
        symbol (str): symbol de trading (ex: "BTC/USDT").
        novo_sl (float): Novo valor de Stop Loss.
    """
    query = """
        UPDATE sinais
        SET sl = %s
        WHERE symbol = %s AND ordem_status_id = 1
    """
    try:
        executar_update(query, (novo_sl, symbol))
        logger.debug(f"✅ - SL atualizado para {symbol}: {novo_sl}")
    except Exception as e:
        logger.exception(f"❌ - Falha ao atualizar SL para {symbol}: {e}")

#Chamado por TelegramReader para marcar o sinal que atingiu TP2 e então ser atualizado por TradeExecutor.py
def stop_loss_ajuste(id_sinal, sl, ativar_break_even: bool):
    """
    Marca o sinal para ajuste de Stop Loss via TradeExecutor.

    - Atualiza o campo `sl` com o valor fornecido.
    - Define `break_even_status_id` como 1 (True) ou 0 (False).
    """
    query = """
        UPDATE sinais 
        SET break_even_status_id = %(break_even)s,
            sl = %(sl)s
        WHERE id = %(id)s
    """
    params = {
        "id": id_sinal,
        "sl": sl,
        "break_even": 1 if ativar_break_even else 0
    }

    executar_update(query, params)

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
        SELECT 
            s.id,
            s.data_hora,
            s.symbol,
            s.tipo_ordem,
            s.margem,
            s.alavancagem,
            s.sl,
            s.ordem_status_id,
            s.break_even_status_id,
            s.order_id,
            s.entry_price,
            s.quantidade,
            s.janela_5min,
            os.descricao AS status_ordem,
            be.descricao AS status_break_even
        FROM 
            public.sinais s
        JOIN 
            public.ordem_status os ON s.ordem_status_id = os.id
        JOIN 
            public.break_even_status be ON s.break_even_status_id = be.id
        ORDER BY 
            s.id DESC
        FOR UPDATE SKIP LOCKED;
    """
    resultado = executar_select(query)
    return resultado if resultado is not None else []

def break_even_soma_quantidade(symbol):
    """
    Soma a quantidade total de sinais com break-even pendente para o symbol.
    break_even_status_id = 1 - ATIVAR
    Args:
        symbol (str): symbol a ser analisado.

    Returns:
        float: Soma das quantidades.
    """
    sql = """
        SELECT SUM(tp.quantidade) AS total
        FROM take_profits tp
        JOIN sinais s ON s.id = tp.sinal_id
        WHERE s.symbol = %(symbol)s 
        AND tp.tp_status_id = 2
          """
    resultado = executar_select(sql, {"symbol": symbol})
    if resultado and resultado[0]["total"] is not None:
        return resultado[0]["total"]
    return 0.0

#MÉTODOS DE CONTROLE DE ORDENS
def ordem_atualizar_tp(sinal_id, numero, quantidade, valor):
    """
    Atualiza o valor e a quantidade de um TP específico, desde que esteja com status CONFIGURADO (tp_status_id = 2).

    Args:
        sinal_id (int): ID do sinal.
        numero (int): Número do TP (1 a 5).
        quantidade (float): Quantidade ajustada.
        valor (float): Novo valor-alvo do TP.
    """

    query = """
        UPDATE take_profits
        SET quantidade = %s, valor = %s
        WHERE sinal_id = %s AND numero = %s AND tp_status_id = 2
    """
    params = (quantidade, valor, sinal_id, numero)
    executar_update(query, params)

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

def ordem_concluir(symbol):
    """
    Marca todos os sinais ativos (ordem_status_id = 1) de um symbol como concluídos (ordem_status_id = 3).

    Args:
        symbol (str): symbol de trading (ex: 'BTC/USDT').
    """
    query = """
        UPDATE sinais
        SET ordem_status_id = 3
        WHERE id IN (
            SELECT id FROM sinais
            WHERE symbol = %(symbol)s AND ordem_status_id = 1
        )
    """
    executar_update(query, {"symbol": symbol})

def ordem_enviar(id_sinal, entry_price, order_id, quantidade):
    """
    Marca um sinal como executado com ordem enviada com sucesso.
    Essa atualização ocorre após confirmação da corretora de que a ordem foi enviada com sucesso.
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

def ordem_info(symbol, exigir_break_even_inativo=False):
    """
    Busca a última ordem enviada para um determinado symbol.

    Se `exigir_break_even_inativo` for True, filtra apenas ordens com break_even_status_id = 0.

    Args:
        symbol (str): symbol de negociação, ex: 'BTC/USDT'.
        exigir_break_even_inativo (bool): Se True, filtra por break_even_status_id = 0.

    Returns:
        dict | None: Registro mais recente da ordem, ou None.
    """
    condicoes = [
        "symbol = %(symbol)s",
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
    resultado = executar_select(query, {"symbol": symbol})
    return resultado[0] if resultado else None


#Insere sinal recebido pelo TelegramReader no banco
def ordem_inserir(dados, take_profits):
    """
    Insere um novo sinal na tabela `sinais` e os TPs correspondentes,
    mas sem definir a quantidade dos TPs neste momento.

    Args:
        dados (dict): Dados do sinal (symbol, tipo_ordem, margem, alavancagem, sl, quantidade, etc.).
        take_profits (list): Lista de dicionários com {numero, valor, proporcao}.

    Returns:
        int: ID do sinal inserido.
    """
    query_sinal = """
        INSERT INTO sinais (
            data_hora, symbol, tipo_ordem, margem, alavancagem,
            sl, quantidade
        ) VALUES (
            %(data_hora)s, %(symbol)s, %(tipo_ordem)s, %(margem)s, %(alavancagem)s,
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

def stop_loss_fire():
    """
    Busca sinais pendentes de execução
    ordem_status_id = 0 - RECEBIDA
    Returns:
        list[dict]: Lista de sinais prontos para envio de ordem.
    """
    query = """
        SELECT 
            s.*,
            (
                SELECT MIN(tp.numero)
                FROM public.take_profits tp
                WHERE tp.sinal_id = s.id
                  AND tp.tp_status_id IN (1, 2)
            ) AS tp_monitorado,
            (
                SELECT SUM(tp.quantidade)
                FROM public.take_profits tp
                WHERE tp.sinal_id = s.id
                  AND tp.tp_status_id IN (1, 2)
            ) AS quantidade
        FROM public.sinais s
        WHERE s.break_even_status_id = 1
          AND s.ordem_status_id = 1
          AND EXISTS (
              SELECT 1
              FROM public.take_profits tp
              WHERE tp.sinal_id = s.id
                AND tp.tp_status_id IN (1, 2)
          )
        ORDER BY s.id DESC;
    """
    resultado = executar_select(query)
    return resultado if resultado is not None else []

def take_profits_atualizar(symbol, numero_tp, novo_status=3, sinal_id=None):
    """
    Atualiza o status de um Take Profit específico de um symbol ou de um sinal_id diretamente.

    Args:
        symbol (str): symbol do sinal (ex: "BTC/USDT").
        numero_tp (int): Número do TP (1 a 5).
        novo_status (int): Novo status (ex: 3 = atingido).
        sinal_id (int or None): ID específico do sinal (opcional).
    """

    if sinal_id is not None:
        query = """
            UPDATE take_profits
            SET tp_status_id = %(status)s
            WHERE id_sinal = %(sinal_id)s
              AND numero = %(numero)s
        """
        params = {"sinal_id": sinal_id, "numero": numero_tp, "status": novo_status}

    else:
        query = """
            UPDATE take_profits
            SET tp_status_id = %(status)s
            WHERE id_sinal IN (
                SELECT id FROM sinais
                WHERE symbol = %(symbol)s AND ordem_status_id = 1
            )
            AND numero = %(numero)s
        """
        params = {"symbol": symbol, "numero": numero_tp, "status": novo_status}

    executar_update(query, params)


def take_profits_por_sinal(sinal_id):
    """
    Retorna os Take Profits cadastrados para um sinal.

    Args:
        sinal_id (int): ID do sinal.

    Returns:
        list[dict]: Lista de TPs ordenada pelo número.
    """

    query = """
        SELECT numero, valor, proporcao FROM take_profits
        WHERE sinal_id = %s
        ORDER BY numero
    """
    return executar_select(query, (sinal_id,))

def take_profits_somar_quantidades_de_take_profits_ativos(symbol):
    """
    Soma a quantidade total de TPs com status 2 (CONFIGURADO)
    para sinais com ordem_status_id = 1 (enviada).

    Args:
        symbol (str): symbol de negociação.

    Returns:
        float: Soma total das quantidades.
    """
    query = """
        SELECT SUM(tp.quantidade) AS total
        FROM take_profits tp
        INNER JOIN sinais s ON tp.sinal_id = s.id
        WHERE s.symbol = %(symbol)s
          AND s.ordem_status_id = 1
          AND tp.tp_status_id IN (1, 2)
    """
    resultado = executar_select(query, {"symbol": symbol})
    if resultado and resultado[0]["total"] is not None:
        return resultado[0]["total"]
    return 0.0