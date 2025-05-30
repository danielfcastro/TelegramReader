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