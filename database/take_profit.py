from database.db import executar_insert, executar_update


def tp_inserir(take_profits):
    """
    Insere múltiplos TPs na tabela `take_profits`.

    Args:
        take_profits (list): Lista de dicionários com:
            numero, valor, quantidade, order_id, status
    """

    query_tp = """
        INSERT INTO take_profits (
            numero, valor, quantidade, order_id, tp_status_id
        ) VALUES (
            %(numero)s, %(valor)s, %(quantidade)s, %(order_id)s, %(status)s
        )
    """

    for tp in take_profits:
        tp_dados = {
            "numero": tp["numero"],
            "valor": tp["valor"],
            "quantidade": tp["quantidade"],
            "order_id": tp["order_id"],
            "status": tp["status"]
        }
        executar_insert(query_tp, tp_dados)

def tp_atualizar(order_id, numero_tp, novo_status=3):
    """
    Atualiza o status de um Take Profit específico de um par.

    Args:
        :param novo_status: Novo status (ex: 3).
        :param numero_tp: ordem ou cardinalidade do TP, cada ordem abre 4 TPs
        :param order_id: id da ordem enviada
    """

    query = """
        UPDATE take_profits
        SET tp_status_id = %(status)s
        WHERE order_id = %(order_id)s
        AND numero = %(numero)s
    """
    params = {"order_id": order_id, "numero": numero_tp, "status": novo_status}
    executar_update(query, params)

def tp_ordem_id_mais_nova(symbol):
    """
    Retorna o order_id mais recente para um determinado symbol,
    com ordem_status_id = 1.

    Args:
        symbol (str): Símbolo do par (ex: BTCUSDT)

    Returns:
        str | None: order_id mais recente ou None se não encontrado
    """
    query = """
        SELECT order_id FROM sinais
        WHERE symbol = %(symbol)s AND ordem_status_id = 1
        ORDER BY janela_5min DESC
        LIMIT 1
    """
    resultado = executar_select_um(query, {"symbol": symbol})
    return resultado["order_id"] if resultado else None



