from database.db import executar_insert


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

    # Insere o sinal e obtém o ID
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