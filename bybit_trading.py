import json
import hmac
import hashlib
import time
import requests
from decimal import Decimal, ROUND_DOWN
import os

from pybit.unified_trading import HTTP


def carregar_config(path='config.properties'):
    config = {}
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo de configuração {path} não encontrado.")
    with open(path, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#') and '=' in linha:
                chave, valor = linha.split('=', 1)
                config[chave.strip()] = valor.strip()
    return config


config = carregar_config()

IS_TESTNET = True

if IS_TESTNET:
    session = HTTP(
        testnet=True,
        api_key=config["bybit_api_key_testnet"],
        api_secret=config["bybit_api_secret_testnet"]
    )
else:
    session = HTTP(
        testnet=False,
        api_key=config["bybit_api_key"],
        api_secret=config["bybit_api_secret"]
    )

def arredondar(valor, casas=4):
    return float(Decimal(valor).quantize(Decimal(10) ** -casas, rounding=ROUND_DOWN))

def obter_saldo_disponivel():
    resposta = session.get_wallet_balance(accountType="UNIFIED")
    usdt = resposta["result"]["list"][0]["coin"]
    for moeda in usdt:
        if moeda["coin"] == "USDT":
            return float(moeda["availableToTrade"])
    raise Exception("Não foi possível obter saldo disponível em USDT.")

def abrir_ordem_com_tps(sinal):
    symbol = sinal["pair"].replace("/", "")
    side = "Buy" if sinal["type"].upper() == "LONG" else "Sell"
    stop_loss = sinal["stoploss"]
    entry_price = sinal["entry_high"]  # usamos preço superior do intervalo
    tps = [sinal.get(f"tp{i}") for i in range(1, 5) if sinal.get(f"tp{i}")]

    trade_pct = float(config.get("trade_percentage", "3"))
    saldo = obter_saldo_disponivel()
    valor_trade = saldo * (trade_pct / 100)

    # Supondo ordem de mercado, pegamos o valor_trade dividido pelo preço de entrada
    quantidade_total = arredondar(valor_trade / entry_price)
    print(f"➡️ Enviando ordem {side} de {quantidade_total} {symbol}...")

    resposta_ordem = session.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        orderType="Market",
        qty=str(quantidade_total),
        timeInForce="IOC",
        orderLinkId=f"{symbol}-entrada"
    )

    print("📦 Ordem enviada:", resposta_ordem)

    if resposta_ordem["retCode"] != 0:
        print("❌ Falha ao enviar ordem.")
        return

    # Divisão em tamanhos fixos [ex: 20%, 30%, 30%, 20%]
    percentuais = [0.2, 0.3, 0.3, 0.2][:len(tps)]
    quantidades = [arredondar(quantidade_total * p) for p in percentuais]

    for i, (tp_price, tp_size) in enumerate(zip(tps, quantidades), start=1):
        resposta_tp = session.set_trading_stop(
            category="linear",
            symbol=symbol,
            takeProfit=str(tp_price),
            stopLoss=str(stop_loss),
            tpTriggerBy="MarkPrice",
            slTriggerBy="MarkPrice",
            tpslMode="Partial",
            tpOrderType="Market",
            slOrderType="Market",
            tpSize=str(tp_size),
            slSize=str(tp_size),
            tpLimitPrice=str(tp_price),
            slLimitPrice=str(stop_loss),
            positionIdx=0
        )
        print(f"✅ TP{i} configurado:", resposta_tp)


# Exemplo de uso direto
if __name__ == "__main__":
    with open("exemplo_sinal.json", "r", encoding="utf-8") as f:
        sinal = json.load(f)
        abrir_ordem_com_tps(sinal)
