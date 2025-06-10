from database.db import executar_update, executar_select

def stop_loss_update(order_id, novo_sl):
    """
    Atualiza o valor do Stop Loss da ordem principal (em execução) associada a um determinado par de trading.

    :param symbol: (str) Par de trading (ex: "BTC/USDT").
    :param novo_sl: (float) Novo valor de Stop Loss a ser definido.
    """
    query = """
        UPDATE v2.ordem
        SET sl = %s
        WHERE order_id = %s AND ordem_status_id = 1
    """
    executar_update(query, (novo_sl, order_id))

def stop_loss_soma_quantidade(order_id):
    """
    Calcula a soma total da quantidade de sinais com break-even pendente
    (ou seja, que ainda não foram executados) para uma determinada ordem.

    Considera apenas os registros na tabela `take_profits` cujo `tp_status_id = 1`.

    :param order_id: (str|int) Identificador da ordem no broker (retornado no momento do envio da ordem).
    :return: (float) Soma total da quantidade pendente de execução para break-even. Retorna 0.0 se nenhum registro encontrado.
    """
    sql = """
    SELECT SUM(quantidade) AS total
    FROM v2.take_profits
    WHERE order_id = %(order_id)s 
      AND tp_status_id = 1
    """
    resultado = executar_select(sql, {"order_id": order_id})
    if resultado and resultado[0]["total"] is not None:
        return resultado[0]["total"]
    return 0.0