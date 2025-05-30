from database.db import executar_insert, executar_select


def ordem_inserir(dados):
    """
    Insere uma nova ordem na tabela `sinais`.

    Args:
        dados (dict): Dados do sinal com os seguintes campos obrigatórios:
            - symbol (str)
            - tipo_ordem (str)
            - margem (str)
            - alavancagem (int)
            - sl (float)
            - quantidade (float)
            - ordem_status_id (int) [opcional, default=2]
            - break_even_status_id (int) [opcional, default=1]
            - order_id (str) [opcional]
            - entry_price (float) [opcional]

    Returns:
        int: ID do sinal inserido.
    """
    query_sinal = """
        INSERT INTO sinais (
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

    # Defaults caso não sejam passados
    dados.setdefault("ordem_status_id", 2)
    dados.setdefault("break_even_status_id", 1)
    dados.setdefault("order_id", None)
    dados.setdefault("entry_price", None)

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
        SELECT * FROM sinais
        WHERE {' AND '.join(condicoes)}
        ORDER BY id DESC
        LIMIT 1
    """
    resultado = executar_select(query, {"par": par})
    return resultado[0] if resultado else None