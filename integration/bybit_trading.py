import os
import time
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from pybit.unified_trading import HTTP

load_dotenv()

api_key = os.getenv("broker_api_key")
api_secret = os.getenv("broker_api_secret")
api_url = os.getenv("broker_api_url")

session = HTTP(
    testnet="testnet" in api_url,
    api_key=api_key,
    api_secret=api_secret
)

def ajustar_quantidade(qty, step):
    step_decimal = Decimal(step)
    qty_decimal = Decimal(str(qty))
    return float((qty_decimal // step_decimal) * step_decimal)

def obter_parametros_simbolo(symbol):
    try:
        response = session.get_instruments_info(category="linear", symbol=symbol)
        if response["retCode"] == 0:
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

def set_break_even(symbol):
    try:
        position = session.get_positions(category="linear", symbol=symbol)
        if position["retCode"] != 0 or not position["result"]["list"]:
            print(f"❌ Não foi possível obter posição ativa para {symbol}")
            return False

        entry_price = float(position["result"]["list"][0]["entryPrice"])
        if entry_price == 0:
            print(f"⚠️ Nenhuma posição ativa para {symbol}.")
            return False

        response = session.set_trading_stop(
            category="linear",
            symbol=symbol,
            stopLoss=str(entry_price),
            slTriggerBy="MarkPrice",
            tpslMode="Full",
            slOrderType="Market",
            positionIdx=0
        )
        print(f"✅ SL movido para break-even ({entry_price}) em {symbol}:", response)
        return True
    except Exception as e:
        print(f"❌ Erro ao mover SL para break-even em {symbol}:", e)
        return False

def abrir_ordem_com_tps(sinal):
    try:
        print("🔐 Consultando saldo para calcular valor do trade...")
        saldo = obter_saldo_disponivel()
        percentual = float(os.getenv("TRADE_PERCENTAGE", "3"))
        valor_trade = saldo * percentual / 100

        print(f"💰 Saldo disponível: {saldo:.2f} USDT — Usando {percentual}% = {valor_trade:.2f} USDT")

        symbol = sinal["pair"].replace("/", "")
        preco_mercado = obter_preco_mercado(symbol)
        if preco_mercado is None:
            print("❌ Não foi possível obter o preço de mercado.")
            return False

        step, min_qty, min_notional = obter_parametros_simbolo(symbol)
        qty = valor_trade / preco_mercado
        qty = max(qty, min_qty)
        qty = ajustar_quantidade(qty, step)

        print(f"➡️ Ordem: {symbol} | Tipo: {sinal['type']} | Preço mercado: {preco_mercado} | Quantidade: {qty}")

        try:
            resposta_inicial = session.place_order(
                category="linear",
                symbol=symbol,
                side="Buy" if sinal["type"] == "LONG" else "Sell",
                orderType="Market",
                qty=str(qty),
                orderLinkId=f"trade_{int(time.time())}",
                timeInForce="IOC",
                isLeverage=0
            )
            print("📥 Ordem de entrada enviada:", resposta_inicial)
        except Exception as e:
            print("Erro ao enviar ordem:", e)
            return False

        proporcoes = [0.2, 0.3, 0.5, 0.2]
        tps = [sinal.get("tp1"), sinal.get("tp2"), sinal.get("tp3"), sinal.get("tp4")]
        quantidades = [ajustar_quantidade(qty * p, step) for p in proporcoes]

        for i, (tp_price, tp_size) in enumerate(zip(tps, quantidades), start=1):
            try:
                resposta_tp = session.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    takeProfit=str(tp_price),
                    stopLoss=str(sinal["stoploss"]),
                    tpTriggerBy="MarkPrice",
                    slTriggerBy="MarkPrice",
                    tpslMode="Partial",
                    tpOrderType="Market",
                    slOrderType="Market",
                    tpSize=str(tp_size),
                    slSize=str(tp_size),
                    positionIdx=0
                )
                print(f"✅ TP{i} configurado:", resposta_tp)
            except Exception as e:
                print(f"❌ Erro ao configurar TP{i}:", e)
                return False

        try:
            valor_posicao = preco_mercado * qty
            sl_diff = preco_mercado - float(sinal["stoploss"])

            if sl_diff * qty < 0.1 * valor_posicao:
                novo_sl = preco_mercado - (0.1 * valor_posicao / qty)
                novo_sl = round(novo_sl, 5)
                print(f"⚠️ SL ajustado para atender mínimo da Bybit: {novo_sl}")
            else:
                novo_sl = sinal["stoploss"]

            resposta_sl = session.set_trading_stop(
                category="linear",
                symbol=symbol,
                stopLoss=str(novo_sl),
                slTriggerBy="MarkPrice",
                tpslMode="Full",
                slOrderType="Market",
                positionIdx=0
            )
            print("🛡️ Stop Loss configurado:", resposta_sl)
        except Exception as e:
            print("❌ Erro ao configurar Stop Loss:", e)
            return False

        return True

    except Exception as e:
        print("❌ Erro inesperado ao abrir ordem:", e)
        return False
