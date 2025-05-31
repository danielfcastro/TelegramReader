from database.db import executar_update, executar_select

def stop_loss_update(symbol, novo_sl):
    """
    Atualiza o Stop Loss da ordem principal de um determinado par.

    Args:
        :param novo_sl: (float): Novo valor de Stop Loss.
        :param symbol: Par de trading (ex: "BTC/USDT").
    """
    query = """
        UPDATE v2.ordem
        SET sl = %s
        WHERE symbol = %s AND ordem_status_id = 1
    """
    executar_update(query, (novo_sl, symbol))

def stop_loss_soma_quantidade(order_id):
    """
    Soma a quantidade total de sinais com break-even pendente para o par.
    break_even_status_id = 1 - ATIVAR
    Args:
        :param order_id: Order ID retornado pelo broker após uma ordem enviada com sucesso

    Returns:
        float: Soma das quantidades.

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