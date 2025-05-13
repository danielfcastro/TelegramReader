import logging
import math
import os
import re

from telethon.errors import ChannelInvalidError, ChatIdInvalidError
from telethon.tl.types import PeerChannel, PeerChat

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

def ajustar_quantidade(qty, step):
    """
        Ajusta a quantidade `qty` para que seja múltipla do `step`, conforme exigência da corretora.

        Args:
            qty (float): Quantidade original desejada.
            step (float): Incremento mínimo aceito (ex: 0.01 ou 0.0001).

        Returns:
            float: Quantidade ajustada e arredondada.
        """
    step = float(step)
    qty_ajustada = math.floor(qty / step) * step
    return round(qty_ajustada, str(step)[::-1].find('.'))

def carregar_config(path='config.properties'):
    """
    Carrega variáveis de configuração de um arquivo `.properties`.

    Args:
        path (str): Caminho do arquivo de configuração. Default: 'config.properties'.

    Returns:
        dict: Dicionário com as configurações carregadas.
    """
    logger.info("🔧 - Carregando configuração do arquivo: %s", path)
    config = {}
    if not os.path.exists(path):
        logger.error(f"❌ - Arquivo de configuração {path} não encontrado.")
        exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#') and '=' in linha:
                chave, valor = linha.split('=', 1)
                config[chave.strip()] = valor.strip()
    logger.info(f"🔧 - Configuração do arquivo: {path} carregado")
    return config

def extrair_dados_mensagem(mensagem):
    """
    Extrai dados estruturados de uma mensagem de sinal do Telegram.

    Args:
        mensagem (str): Texto da mensagem contendo sinal de trade.

    Returns:
        dict: Dicionário com dados como par, tipo de ordem, SL, TP1..TP4, margem e alavancagem.
    """
    logger.debug("📩 - Analisando mensagem completa:")
    logger.debug(f"\n{mensagem}")

    dados = {}

    # Extração comum
    pair_match = re.search(r"([A-Z0-9]+/USDT)", mensagem)
    type_match = re.search(r"(LONG|BUY|SHORT|SELL)", mensagem, re.IGNORECASE)
    sl_match = re.search(r"\*\*STOPLOSS:\*\*\s*\[`?([0-9\.]+)`?\]", mensagem, re.IGNORECASE)
    margin_match = re.search(r"Margin:\s*(\w+),\s*(\d+)X", mensagem, re.IGNORECASE)
    targets = re.findall(r"\[`?([0-9\.]+)`?\]", mensagem)
    target_done = re.search(r"TARGET #(\d) DONE", mensagem, re.IGNORECASE)

    if pair_match:
        dados["pair"] = pair_match.group(1).upper()
    if type_match:
        dados["type"] = type_match.group(1).upper()
    if sl_match:
        dados["stoploss"] = float(sl_match.group(1))
    if margin_match:
        dados["margin"] = margin_match.group(1).capitalize()
        dados["leverage"] = margin_match.group(2) + "X"
    if target_done:
        dados["tp"] = f"TP{target_done.group(1)}"
    for i, alvo in enumerate(targets[:4], start=1):
        dados[f"tp{i}"] = float(alvo)

    logger.debug("🔎 - Par: %s", pair_match.group(1) if pair_match else "N/A")
    logger.debug("🔎 - Tipo: %s", type_match.group(1) if type_match else "N/A")
    logger.debug("🔎 - SL: %s", sl_match.group(1) if sl_match else "N/A")
    logger.debug("🔎 - Targets extraídos: %s", ', '.join(targets) if targets else "N/A")
    logger.debug("🔎 - TARGET: %s DONE", dados.get("tp", "N/A"))
    logger.debug("🔎 - Margem: %s", margin_match.groups() if margin_match else "N/A")
    logger.debug("🔎 - Target monitorado: %s", target_done.group(1) if target_done else "N/A")

    return dados

def classificar_mensagem(mensagem):
    """
    Classifica a mensagem como 'trade', 'monitoramento' ou 'desconhecido'.

    Args:
        mensagem (str): Texto da mensagem.

    Returns:
        dict: Dicionário com chave 'tipo' e os 'dados' extraídos.
    """
    dados = extrair_dados_mensagem(mensagem)
    _msg = {}

    if "type" in dados and "stoploss" in dados:
        _msg = {"tipo": "trade", "dados": dados}
    elif "tp" in dados:
        _msg = {"tipo": "monitoramento", "dados": {
            "pair": dados.get("pair", "N/A"),
            "tp": dados["tp"]
        }}
    else:
        _msg = {"tipo": "desconhecido", "dados": dados}

    return _msg

def limpar_nome(nome):
    """
    Limpa e formata um nome de arquivo ou pasta removendo caracteres inválidos.

    Args:
        nome (str): Nome original.

    Returns:
        str: Nome formatado com apenas letras, números, hífens e underscores.
    """
    nome = nome.replace(' ', '_')
    nome = re.sub(r'[^A-Za-z0-9_\-]', '', nome)
    return nome

def criar_pasta(path):
    """
    Cria uma pasta se ela ainda não existir.

    Args:
        path (str): Caminho da pasta a ser criada.
    """
    if not os.path.exists(path):
        os.makedirs(path)

async def obter_entidade(client, id_input):
    """
    Obtém uma entidade de grupo ou canal do Telegram, tratando diferentes tipos de ID.

    Args:
        client (TelegramClient): Cliente ativo do Telethon.
        id_input (int | str): ID do grupo ou canal.

    Returns:
        telethon.tl.custom.chat.Chat | None: Entidade correspondente, ou None se não encontrada.
    """
    try:
        return await client.get_entity(PeerChannel(int(id_input)))
    except (ChannelInvalidError, ValueError):
        pass
    try:
        return await client.get_entity(PeerChat(int(id_input)))
    except (ChatIdInvalidError, ValueError):
        pass
    return None

def imprimir_configuracoes_ambiente():
    """
    Exibe no log as principais variáveis de ambiente de execução e status do ambiente (testnet/mainnet).
    """
    logger.info("📄 - Variáveis de ambiente definidas:")
    for chave in ["BROKER", "IS_TESTNET", "trade_percentage", "bybit_api_key", "bybit_api_secret", "bybit_api_url"]:
        valor = os.getenv(chave)
        logger.info("   %s=%s", chave, valor)

    is_testnet = os.getenv("IS_TESTNET", "false").strip('"').lower() == "true"
    logger.info("🚦- Iniciando componentes...")
    logger.info("🚀 - Executando trade no broker: %s (Testnet=%s)", os.getenv('BROKER', '').upper(), is_testnet)
    logger.info("🔐 - Consultando saldo para calcular valor do trade...")

def extrair_limite_usdt(mensagem):
    """
    Extrai o valor máximo de exposição (em USDT) a partir de uma mensagem de erro da corretora.

    Args:
        mensagem (str): Texto da mensagem de erro.

    Returns:
        float | None: Valor do limite em USDT se encontrado, ou None.
    """
    match = re.search(r'position limit of (\d+(?:\.\d+)?)\s*USDT', mensagem)
    if match:
        return float(match.group(1))
    return None