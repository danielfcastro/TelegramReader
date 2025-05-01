import math
import os
import time
from decimal import Decimal, ROUND_DOWN, getcontext
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

api_key = os.getenv("BROKER_API_KEY")
api_secret = os.getenv("BROKER_API_SECRET")
api_url = os.getenv("BROKER_API_URL")

session = HTTP(
    testnet="testnet" in api_url,
    api_key=api_key,
    api_secret=api_secret
)

proporcoes = [0.1, 0.2, 0.5, 0.1]

def ajustar_quantidade(qty, step):
    step = float(step)
    qty_ajustada = math.floor(qty / step) * step
    return round(qty_ajustada, str(step)[::-1].find('.'))

def obter_parametros_simbolo(symbol):
    try:
        response = session.get_instruments_info(category="linear", symbol=symbol)
        if response["retCode"] == 0 and response["result"]["list"]:
            item = response["result"]["list"][0]
            filtro = item["lotSizeFilter"]
            step = filtro["qtyStep"]
            min_qty = filtro["minOrderQty"]
            min_notional = float(filtro.get("minNotionalValue", 5))
            print(f"🧩 Parâmetros do símbolo {symbol} — Step: {step}, MinQty: {min_qty}, MinNotional: {min_notional}")
            return float(step), float(min_qty), float(min_notional)
    except Exception as e:
        print("Erro ao obter parâmetros do símbolo:", e)
    raise Exception("Não foi possível obter parâmetros do símbolo.")

def obter_preco_mercado(symbol):
    try:
        response = session.get_tickers(category="linear", symbol=symbol)
        if response["retCode"] == 0:
            return float(response["result"]["list"][0]["lastPrice"])
    except Exception as e:
        print("Erro ao obter preço de mercado:", e)
    return None

def obter_saldo_disponivel():
    try:
        response = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        print("🧾 Resposta da API:", response)
        if response["retCode"] == 0:
            conta = response["result"]["list"][0]
            return float(conta.get("totalAvailableBalance") or 0.0)
    except Exception as e:
        print("Erro ao consultar saldo:", e)
    raise Exception("Não foi possível obter saldo disponível em USDT.")

def enviar_ordem_sem_tp_sl(sinal):
    symbol = sinal["pair"].replace("/", "")
    preco_mercado = obter_preco_mercado(symbol)
    if preco_mercado is None:
        print(f"❌ Não foi possível obter preço para enviar ordem de {symbol}")
        return False

    try:
        step, min_qty, _ = obter_parametros_simbolo(symbol)
        saldo = obter_saldo_disponivel()
        valor_trade = saldo * float(os.getenv("TRADE_PERCENTAGE", "3")) / 100
        qty = valor_trade / preco_mercado
        qty = max(qty, min_qty)
        qty = ajustar_quantidade(qty, step)

        side = "Buy" if sinal["type"].upper() == "LONG" else "Sell"

        # NOVO: extrair tradeMode e leverage do sinal
        margin = sinal["margem"].lower()
        trade_mode = 0 if "cross" in margin else 1

        leverage_str = sinal.get("alavancagem", "1X").replace("X", "")
        leverage = int(leverage_str) if leverage_str.isdigit() else 1

        response = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=str(qty),
            orderLinkId=f"trade_{int(time.time())}",
            timeInForce="IOC",
            isLeverage=0,
            tradeMode=trade_mode,
            leverage=leverage,
        )

        print(f"📥 Ordem enviada: {response}")
        return response["retCode"] == 0
    except Exception as e:
        print("❌ Erro ao enviar ordem:", e)
        return False


def configurar_take_profits(sinal):
    try:
        symbol = sinal["pair"].replace("/", "")
        preco_mercado = obter_preco_mercado(symbol)
        if preco_mercado is None:
            print(f"❌ Não foi possível obter preço para TP de {symbol}")
            return False

        step, min_qty, _ = obter_parametros_simbolo(symbol)
        saldo = obter_saldo_disponivel()
        valor_trade = saldo * float(os.getenv("TRADE_PERCENTAGE", "3")) / 100
        qty = max(valor_trade / preco_mercado, min_qty)
        qty = ajustar_quantidade(qty, step)

        tps = [sinal.get("tp1"), sinal.get("tp2"), sinal.get("tp3"), sinal.get("tp4")]
        quantidades = [ajustar_quantidade(qty * p, step) for p in proporcoes]

        sucesso = True
        for i, (tp_price, tp_size) in enumerate(zip(tps, quantidades), start=1):
            try:
                response = session.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    takeProfit=str(tp_price),
                    stopLoss=str(sinal["stoploss"]),  # necessário pela API
                    tpTriggerBy="MarkPrice",
                    slTriggerBy="MarkPrice",
                    tpslMode="Partial",
                    tpOrderType="Market",
                    slOrderType="Market",
                    tpSize=str(tp_size),
                    slSize=str(tp_size),
                    positionIdx=0
                )
                print(f"✅ TP{i} configurado:", response)
            except Exception as e:
                sucesso = False
                print(f"❌ Erro ao configurar TP{i}:", e)
        return sucesso
    except Exception as e:
        print("Erro geral no configurar_take_profits:", e)
        return False


def configurar_stop_loss(sinal):
    try:
        symbol = sinal["pair"].replace("/", "")
        response = session.set_trading_stop(
            category="linear",
            symbol=symbol,
            stopLoss=str(sinal["stoploss"]),
            slTriggerBy="MarkPrice",
            tpslMode="Full",
            slOrderType="Market",
            positionIdx=0
        )
        print("🛡️ Stop Loss configurado:", response)
        return response.get("retCode") == 0
    except Exception as e:
        print("❌ Erro ao configurar SL total:", e)
        return False


def set_break_even(symbol):
    try:
        position = session.get_positions(category="linear", symbol=symbol)
        if position["retCode"] != 0 or not position["result"]["list"]:
            print(f"❌ Sem posição ativa para {symbol}")
            return

        entry_price = float(position["result"]["list"][0]["entryPrice"])
        if entry_price == 0:
            print(f"⚠️ Entry price 0 para {symbol}")
            return

        response = session.set_trading_stop(
            category="linear",
            symbol=symbol,
            stopLoss=str(entry_price),
            slTriggerBy="MarkPrice",
            tpslMode="Full",
            slOrderType="Market",
            positionIdx=0
        )
        print(f"✅ SL movido para break-even ({entry_price}) em {symbol}")
    except Exception as e:
        print(f"❌ Erro ao mover SL para break-even em {symbol}:", e)
