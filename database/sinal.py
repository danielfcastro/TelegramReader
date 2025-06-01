from database.db import executar_insert, executar_select

def ordem_inserir(dados_dict, order_id, entry_price, quantidade):
    """
    Insere uma nova ordem na tabela `sinais` com dados provenientes da ordem real enviada ao broker.

    :param dados_dict: Dicionário com os dados do sinal. Deve conter:
        - symbol (str): Par de negociação (ex: 'BTC-USDT').
        - tipo_ordem (str): Tipo da ordem (ex: 'buy', 'sell').
        - margem (str): Tipo de margem utilizada (ex: 'isolated', 'cross').
        - alavancagem (int): Fator de alavancagem aplicado.
        - sl (float): Valor de Stop Loss.
    :param order_id: ID da ordem retornado pela corretora.
    :param entry_price: Preço médio de execução da ordem.
    :param quantidade: Quantidade executada na ordem.
    :return: ID do sinal inserido na tabela.
    """
    dados = {
        "symbol": dados_dict["symbol"],
        "tipo_ordem": dados_dict["tipo_ordem"],
        "margem": dados_dict["margem"],
        "alavancagem": dados_dict["alavancagem"],
        "sl": dados_dict["sl"],
        "quantidade": quantidade,
        "ordem_status_id": 2,
        "break_even_status_id": 1,
        "order_id": order_id,
        "entry_price": entry_price
    }

    query_sinal = """
        INSERT INTO v2.ordem (
            data_hora,
            symbol,
            tipo_ordem,
            margem,
            alavancagem,
            sl,
            quantidade,
            ordem_status_id,
            break_even_status_id,
            order_id,
            entry_price
        ) VALUES (
            NOW(),
            %(symbol)s,
            %(tipo_ordem)s,
            %(margem)s,
            %(alavancagem)s,
            %(sl)s,
            %(quantidade)s,
            %(ordem_status_id)s,
            %(break_even_status_id)s,
            %(order_id)s,
            %(entry_price)s
        ) RETURNING id
    """

    sinal_id = executar_insert(query_sinal, dados)
    return sinal_id


def ordem_info(par, exigir_break_even_inativo=False):
    """
    Retorna a ordem ativa mais recente para o par fornecido.

    Pode aplicar filtro adicional para retornar apenas ordens sem break-even ativo.

    :param par: Par de negociação (ex: 'BTC-USDT').
    :param exigir_break_even_inativo: Se True, restringe a busca a ordens com break_even_status_id = 0.
    :return: Dicionário com os dados da ordem encontrada, ou None se não houver.
    """
    condicoes = [
        "par = %(par)s",
        "ordem_status_id = 1",
        "order_id != 0"
    ]

    if exigir_break_even_inativo:
        condicoes.append("break_even_status_id = 0")

    query = f"""
        SELECT * FROM v2.ordem
        WHERE {' AND '.join(condicoes)}
        ORDER BY id DESC
        LIMIT 1
    """
    resultado = executar_select(query, {"par": par})
    return resultado[0] if resultado else None