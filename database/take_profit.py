import logging
import os
from database.db import executar_insert, executar_update, executar_select

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])




def tp_inserir(take_profits):
    """
    Insere múltiplos registros de Take Profit (TP) na tabela `take_profits`.

    :param take_profits: Lista de dicionários representando TPs a serem inseridos.
                         Cada dicionário deve conter:
                         - numero (int): número do TP (ex: 1, 2, 3, 4).
                         - valor (float): valor de disparo do TP.
                         - quantidade (float): quantidade da posição correspondente.
                         - order_id (str): identificador da ordem associada.
                         - status (int): status do TP (ex: 1 = configurado).
    """

    query_tp = """
        INSERT INTO v2.take_profits (
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

def tp_atualizar(order_id, numero_tp, novo_status=1):
    """
    Atualiza o status de um Take Profit específico associado a uma ordem.

    :param order_id: ID da ordem à qual o TP está vinculado.
    :param numero_tp: Número do TP a ser atualizado (ex: 1, 2, 3, 4).
    :param novo_status: Novo status a ser definido para o TP.
                        (1 = configurado, 2 = atingido, 3 = em execução, etc.)
    """

    query = """
        UPDATE v2.take_profits
        SET tp_status_id = %(status)s
        WHERE order_id = %(order_id)s
        AND numero = %(numero)s
    """
    params = {"order_id": order_id, "numero": numero_tp, "status": novo_status}
    executar_update(query, params)

def tp_ordem_id_mais_nova(symbol):
    """
    Retorna o `order_id` mais recente de uma ordem ativa (status 1) para um determinado par (symbol).

    :param symbol: Símbolo do par (ex: 'BTCUSDT').
    :return: `order_id` da ordem mais recente com `ordem_status_id = 1`, ou 0 se não encontrado.
    """
    query = """
        SELECT order_id FROM v2.ordem
        WHERE symbol = %(symbol)s AND ordem_status_id = 1
        ORDER BY data_hora DESC
        LIMIT 1
    """
    resultado = executar_select(query, {"symbol": symbol})
    return resultado["order_id"] if resultado else 0
