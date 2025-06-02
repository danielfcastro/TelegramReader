import logging
import math
import os
import re

from telethon.errors import ChannelInvalidError, ChatIdInvalidError
from telethon.tl.types import PeerChannel, PeerChat
from message.mensagem_sinal import MensagemSinal
from message.mensagem_tp import MensagemTP

regex_target_done = r"TARGET #(\d) DONE"
regex_margem = r"Margin:\s*(\w+),\s*(\d+)X"
regex_stoploss = r"\*\*STOPLOSS:\*\*\s*\[`?([0-9\.]+)`?\]"
regex_type = r"(LONG|BUY|SHORT|SELL)"
regex_symbol = r"([A-Z0-9]+/USDT)"
regex_targets = r"\[`?([0-9\.]+)`?\]"

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

def ajustar_quantidade(qty, step):
    """
    Ajusta a quantidade `qty` para que seja múltipla do `step`, conforme exigência da corretora.

    :param qty: Quantidade original desejada.
    :param step: Incremento mínimo aceito (ex: 0.01 ou 0.0001).
    :return: Quantidade ajustada e arredondada.
    """
    step = float(step)
    qty_ajustada = math.floor(qty / step) * step
    return round(qty_ajustada, str(step)[::-1].find('.'))

def carregar_config(path='config.properties'):
    """
    Carrega variáveis de configuração de um arquivo `.properties`.

    :param path: Caminho do arquivo de configuração. Default: 'config.properties'.
    :return: Dicionário com as configurações carregadas.
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

    :param mensagem: Texto da mensagem contendo sinal de trade.
    :return: Dicionário com dados como symbol, tipo de ordem, SL, TP1..TP4, margem e alavancagem.
    """
    logger.debug("📩 - Analisando mensagem completa:")
    logger.debug(f"\n{mensagem}")

    dados = {}

    # Extração comum
    symbol = re.search(regex_symbol, mensagem)
    type_match = re.search(regex_type, mensagem, re.IGNORECASE)
    sl_match = re.search(regex_stoploss, mensagem, re.IGNORECASE)
    margem_match = re.search(regex_margem, mensagem, re.IGNORECASE)
    targets = re.findall(regex_targets, mensagem)
    target_done = re.search(regex_target_done, mensagem, re.IGNORECASE)

    if symbol:
        dados["symbol"] = normalizar_symbol(symbol.group(1).upper())
    if type_match:
        dados["tipo_ordem"] = type_match.group(1).upper()
    if sl_match:
        stop = float(sl_match.group(1))
        if stop <= 0:
            raise ValueError(f"❌ Stop Loss inválido: {stop}")
        dados["sl"] = stop
    if margem_match:
        dados["margem"] = margem_match.group(1).capitalize()
        dados["alavancagem"] = margem_match.group(2) + "X"
    if target_done:
        dados["tp"] = f"TP{target_done.group(1)}"
    for i, alvo in enumerate(targets[:4], start=1):
        valor = float(alvo)
        if valor <= 0:
            raise ValueError(f"❌ Valor inválido para TP{i}: {valor}")
        dados[f"tp{i}"] = valor

    logger.debug("🔎 - Par: %s", symbol.group(1) if symbol else "N/A")
    logger.debug("🔎 - Tipo: %s", type_match.group(1) if type_match else "N/A")
    logger.debug("🔎 - SL: %s", sl_match.group(1) if sl_match else "N/A")
    logger.debug("🔎 - Targets extraídos: %s", ', '.join(targets) if targets else "N/A")
    logger.debug("🔎 - TARGET: %s DONE", dados.get("tp", "N/A"))
    logger.debug("🔎 - Margem: %s", margem_match.groups() if margem_match else "N/A")
    logger.debug("🔎 - Target monitorado: %s", target_done.group(1) if target_done else "N/A")

    return dados

def classificar_mensagem(mensagem):
    try:
        dados = extrair_dados_mensagem(mensagem)
    except ValueError as e:
        logger.error(f"❌ Erro ao extrair mensagem: {e}")
        return {"tipo": "invalida", "erro": str(e), "dados": {}}

    if "tipo_ordem" in dados and "sl" in dados:
        try:
            msg = MensagemSinal(**dados)
            return {"tipo": "trade", "dados": msg.to_dict()}
        except TypeError as e:
            logger.error(f"❌ Erro ao construir MensagemSinal: {e}")
            return {"tipo": "invalida", "erro": str(e), "dados": dados}
    elif "tp" in dados:
        try:
            msg = MensagemTP(**dados)
            return {"tipo": "monitoramento", "dados": msg.to_dict()}
        except TypeError as e:
            logger.error(f"❌ Erro ao construir MensagemTP: {e}")
            return {"tipo": "invalida", "erro": str(e), "dados": dados}
    else:
        return {"tipo": "desconhecido", "dados": dados}


def normalizar_symbol(symbol: str) -> str:
    """
    Normaliza o símbolo de trading para o formato esperado pela API: BTC-USDT.
    Substitui '/' por '-', e garante caixa alta.

    :param symbol: Símbolo original (ex: BTC/USDT).
    :return: Símbolo normalizado (ex: BTC-USDT).
    """
    return symbol.upper().replace("/", "-")

def limpar_nome(nome):
    """
    Limpa e formata um nome de arquivo ou pasta removendo caracteres inválidos.

    :param nome: Nome original.
    :return: Nome formatado com apenas letras, números, hífens e underscores.
    """
    nome = nome.replace(' ', '_')
    nome = re.sub(r'[^A-Za-z0-9_\-]', '', nome)
    return nome

def criar_pasta(path):
    """
    Cria uma pasta se ela ainda não existir.

    :param path: Caminho da pasta a ser criada.
    """
    if not os.path.exists(path):
        os.makedirs(path)

async def obter_entidade(client, id_input):
    """
    Obtém uma entidade de grupo ou canal do Telegram, tratando diferentes tipos de ID.

    :param client: Cliente ativo do Telethon.
    :param id_input: ID do grupo ou canal (int ou str).
    :return: Entidade correspondente (PeerChannel ou PeerChat) ou None.
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
    logger.info("📈- Iniciando componentes...")
    logger.info("🚀 - Executando trade no broker: %s (Testnet=%s)", os.getenv('BROKER', '').upper(), is_testnet)