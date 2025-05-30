from database.db import executar_update


def stop_loss_update(symbol, novo_sl):
    """
    Atualiza o Stop Loss da ordem principal de um determinado par.

    Args:
        :param novo_sl: (float): Novo valor de Stop Loss.
        :param symbol: Par de trading (ex: "BTC/USDT").
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

def stop_loss_soma_quantidade(symbol):
    """
    Soma a quantidade total de sinais com break-even pendente para o par.
    break_even_status_id = 1 - ATIVAR
    Args:
        :param symbol: Par a ser analisado.

    Returns:
        float: Soma das quantidades.

    """
    sql = """
    SELECT SUM(quantidade) AS total
    FROM sinais
    WHERE symbol = %(symbol)s 
      AND break_even_status_id = 1
      AND ordem_status_id = 1
    """
    resultado = executar_select(sql, {"symbol": symbol})
    if resultado and resultado[0]["total"] is not None:
        return resultado[0]["total"]
    return 0.0