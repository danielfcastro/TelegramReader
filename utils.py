import os
import re
import math
from telethon.tl.types import PeerChannel, PeerChat
from telethon.errors import ChannelInvalidError, ChatIdInvalidError

def ajustar_quantidade(qty, step):
    step = float(step)
    qty_ajustada = math.floor(qty / step) * step
    return round(qty_ajustada, str(step)[::-1].find('.'))

def carregar_config(path='config.properties'):
    config = {}
    if not os.path.exists(path):
        print(f"Arquivo de configuração {path} não encontrado.")
        exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#') and '=' in linha:
                chave, valor = linha.split('=', 1)
                config[chave.strip()] = valor.strip()
    return config

import re

def extrair_sinal_trade(mensagem):
    try:
        pair_match = re.search(r"\[([A-Z0-9]+/USDT)\]", mensagem)
        type_match = re.search(r"\*\*(LONG|BUY|SHORT|SELL)\*\*", mensagem, re.IGNORECASE)
        entry_match = re.search(r"ENTRY:\s*[<\[]?([0-9\.]+)-([0-9\.]+)[>\]]?", mensagem, re.IGNORECASE)
        sl_match = re.search(r"STOPLOSS:\s*[\[]?([0-9\.]+)[\]]?", mensagem, re.IGNORECASE)
        margin_match = re.search(r"Margin:\s*(\w+),\s*(\d+)X", mensagem, re.IGNORECASE)
        targets = re.findall(r"\[\`?([0-9\.]+)\`?\]", mensagem)

        if not (pair_match and type_match and entry_match and sl_match):
            return None

        sinal = {
            "pair": pair_match.group(1).upper(),
            "type": type_match.group(1).upper(),
            "entry_low": float(entry_match.group(1)),
            "entry_high": float(entry_match.group(2)),
            "stoploss": float(sl_match.group(1)),
        }

        if margin_match:
            sinal["margin"] = margin_match.group(1).capitalize()
            sinal["leverage"] = margin_match.group(2) + "X"

        for i, alvo in enumerate(targets[:4], start=1):
            sinal[f"tp{i}"] = float(alvo)

        return sinal
    except Exception as e:
        print("Erro ao extrair sinal:", e)
        return None

def extrair_monitoramento_json(mensagem):
    try:
        pair_match = re.search(r"([A-Z0-9]+/USDT)", mensagem)
        price_match = re.search(r"Price[: ]*([0-9\.]+)", mensagem)
        profit_match = re.search(r"Profit[: ]*>? *([0-9]+)%", mensagem)
        target_done = re.search(r"TARGET #(\d) DONE", mensagem)
        spent_match = re.search(r"Spent[: ]*(\d+d:\d+h:\d+m)", mensagem)
        instrucoes = re.findall(r"\*([^\n\*]+)", mensagem)

        if not (pair_match and price_match and profit_match):
            return None

        monitoramento = {
            "pair": pair_match.group(1),
            "price": float(price_match.group(1)),
            "profit": int(profit_match.group(1)),
            "tp": f"TP{target_done.group(1)}" if target_done else None,
            "spent": spent_match.group(1) if spent_match else None,
            "instructions": [i.strip() for i in instrucoes if i.strip()]
        }
        return monitoramento
    except Exception:
        return None

def limpar_nome(nome):
    nome = nome.replace(' ', '_')
    nome = re.sub(r'[^A-Za-z0-9_\-]', '', nome)
    return nome

def criar_pasta(path):
    if not os.path.exists(path):
        os.makedirs(path)

async def obter_entidade(client, id_input):
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
    print("\n📄 Variáveis de ambiente definidas:")
    for chave in ["BROKER", "IS_TESTNET", "trade_percentage", "bybit_api_key", "bybit_api_secret", "bybit_api_url"]:
        valor = os.getenv(chave)
        print(f"   {chave}={valor}")

    is_testnet = os.getenv("IS_TESTNET", "false").strip('"').lower() == "true"
    print("\n🚦 Iniciando componentes...")
    print(f"🚀 Executando trade no broker: {os.getenv('BROKER', '').upper()} (Testnet={is_testnet})")
    print("🔐 Consultando saldo para calcular valor do trade...")