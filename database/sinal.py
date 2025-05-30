from database.db import executar_insert, executar_select


def ordem_inserir(dados_dict, order_id, entry_price, quantidade):
    """
    Insere uma nova ordem na tabela `sinais` com dados provenientes da ordem real enviada ao broker.

    Args:
        dados_dict (dict): Dados do sinal com os seguintes campos obrigatórios:
            - symbol (str)
            - tipo_ordem (str)
            - margem (str)
            - alavancagem (int)
            - sl (float)

        order_id (str): ID da ordem retornado pelo broker.
        entry_price (float): Preço médio da ordem executada.
        quantidade (float): Quantidade executada na ordem.

    Returns:
        int: ID do sinal inserido.
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
        SELECT * FROM v2.ordem
        WHERE {' AND '.join(condicoes)}
        ORDER BY id DESC
        LIMIT 1
    """
    resultado = executar_select(query, {"par": par})
    return resultado[0] if resultado else None