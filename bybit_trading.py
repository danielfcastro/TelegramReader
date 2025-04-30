import os
import time
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

api_key = os.getenv("bybit_api_key")
api_secret = os.getenv("bybit_api_secret")
api_url = os.getenv("bybit_api_url")
trade_percentage = float(os.getenv("trade_percentage", "3"))

session = HTTP(
    testnet="testnet" in api_url,
    api_key=api_key,
    api_secret=api_secret
)

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

def obter_preco_mercado(symbol):
    try:
        response = session.get_tickers(category="linear", symbol=symbol)
        if response["retCode"] == 0:
            preco = float(response["result"]["list"][0]["lastPrice"])
            print(f"✅ Preço de mercado atual para {symbol}: {preco}")
            return preco
    except Exception as e:
        print(f"Erro ao obter o preço de mercado: {e}")
    return None

def obter_info_instrumento(symbol):
    try:
        response = session.get_instruments_info(category="linear", symbol=symbol)
        if response["retCode"] == 0 and response["result"]["list"]:
            return response["result"]["list"][0]
    except Exception as e:
        print(f"Erro ao obter informações do símbolo {symbol}: {e}")
    return None

def arredondar_quantidade(qty, step):
    return round(qty - (qty % step), 6)

def abrir_ordem_com_tps(sinal):
    print("🔐 Consultando saldo para calcular valor do trade...")
    saldo = obter_saldo_disponivel()
    valor_trade = saldo * trade_percentage / 100

    print(f"💰 Saldo disponível: {saldo:.2f} USDT — Usando {trade_percentage}% = {valor_trade:.2f} USDT")

    symbol = sinal["pair"].replace("/", "").upper()
    preco_mercado = obter_preco_mercado(symbol)
    if preco_mercado is None:
        print("❌ Não foi possível obter o preço de mercado.")
        return

    info = obter_info_instrumento(symbol)
    if not info:
        print(f"❌ Não foi possível obter info do símbolo {symbol}")
        return

    qty_step = float(info["lotSizeFilter"]["qtyStep"])
    min_qty = float(info["lotSizeFilter"]["minOrderQty"])
    min_notional = float(info["lotSizeFilter"]["minNotionalValue"])

    print(f"🧩 Parâmetros do símbolo {symbol} — Step: {qty_step}, MinQty: {min_qty}, MinNotional: {min_notional}")

    qty = valor_trade / preco_mercado
    qty = arredondar_quantidade(qty, qty_step)
    notional = qty * preco_mercado

    if qty < min_qty or notional < min_notional:
        print(f"❌ Quantidade {qty} ou valor notional {notional} abaixo do mínimo exigido.")
        return

    stop_loss = sinal["stoploss"]
    print(f"➡️ Ordem: {symbol} | Tipo: {sinal['type']} | Preço mercado: {preco_mercado} | Quantidade: {qty} | Stop Loss: {stop_loss}")

    try:
        resposta_inicial = session.place_order(
            category="linear",
            symbol=symbol,
            side="Buy" if sinal["type"] == "LONG" else "Sell",
            orderType="Market",
            qty=str(qty),
            orderLinkId=f"trade_{int(time.time())}",
            timeInForce="IOC",
            positionIdx=0  # <= ESSENCIAL
        )
        print("📥 Ordem de entrada enviada:", resposta_inicial)
    except Exception as e:
        print("❌ Erro ao enviar ordem:", e)
        return

    tps = [sinal.get("tp1"), sinal.get("tp2"), sinal.get("tp3"), sinal.get("tp4")]
    proporcoes = [0.1, 0.2, 0.5, 0.2]
    quantidades = [round(qty * p, 3) for p in proporcoes]

    

   # Enviar apenas os TPs com modo Partial
    for i, (tp_price, tp_size) in enumerate(zip(tps, quantidades), start=1):
        try:
            resposta_tp = session.set_trading_stop(
                category="linear",
                symbol=symbol,
                takeProfit=str(tp_price),
                tpTriggerBy="MarkPrice",
                tpslMode="Partial",
                tpOrderType="Market",
                tpSize=str(tp_size),
                positionIdx=0
            )
            print(f"✅ TP{i} configurado:", resposta_tp)
        except Exception as e:
            print(f"❌ Erro ao configurar TP{i}:", e)

    # Enviar o SL em uma chamada separada com modo Full
    try:
        resposta_sl = session.set_trading_stop(
            category="linear",
            symbol=symbol,
            stopLoss=str(stop_loss),
            slTriggerBy="MarkPrice",
            tpslMode="Full",
            slOrderType="Market",
            positionIdx=0
        )
        print("🛡️ Stop Loss configurado:", resposta_sl)
    except Exception as e:
        print("❌ Erro ao configurar Stop Loss:", e)
