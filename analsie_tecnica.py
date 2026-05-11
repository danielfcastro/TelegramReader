import requests
import json
import sys
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
BINGX_URL = os.getenv("broker_api_url", "https://open-api-vst.bingx.com")

def _get_klines(symbol, interval, limit=60):
    url = f"{BINGX_URL}/openApi/swap/v2/quote/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        logger.debug(f"📊 - Buscando klines: {symbol} | TF: {interval} | URL: {url}")
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        if data.get("code") != 0:
            logger.error(f"❌ - Erro API BingX ao buscar klines ({interval}): {data}")
            return None
        closes = [float(c["close"]) for c in data["data"]]
        logger.debug(f"✅ - {len(closes)} klines obtidas para {symbol} ({interval})")
        return closes
    except Exception as e:
        logger.exception(f"❌ - Exceção ao buscar klines para {symbol} ({interval}): {e}")
        return None

def calc_ema(closes, period):
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 8)

def tendencia(closes, label):
    ema9  = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    ema50 = calc_ema(closes, 50)

    if None in [ema9, ema21, ema50]:
        return {"tf": label, "tendencia": "INDISPONIVEL", "ema9": None, "ema21": None, "ema50": None}

    if ema9 > ema21 > ema50:
        t = "ALTA"
    elif ema9 < ema21 < ema50:
        t = "BAIXA"
    else:
        t = "LATERAL"

    return {"tf": label, "tendencia": t, "ema9": ema9, "ema21": ema21, "ema50": ema50}

def check_polymarket(symbol):
    base = symbol.split("-")[0].lower()
    try:
        url = f"https://gamma-api.polymarket.com/events?keyword={base}&active=true&limit=5"
        r = requests.get(url, timeout=5)
        eventos = r.json()
        for evento in eventos:
            for m in evento.get("markets", []):
                title = m.get("question", "").lower()
                if base in title:
                    prob = m.get("outcomePrices", ["0.5"])[0]
                    return {"mercado": m.get("question"), "prob_yes": float(prob)}
    except Exception:
        return None
    return None

def analisar(symbol, tipo_ordem):
    logger.info(f"🔍 - Iniciando análise técnica: {symbol} | Operação: {tipo_ordem}")
    tfs = {"15m": "15m", "1h": "1h", "4h": "4h"}
    resultados = {}
    confluencia = True
    motivo_rejeicao = []

    for label, interval in tfs.items():
        closes = _get_klines(symbol, interval)
        if not closes:
            logger.warning(f"⚠️ - TF {label} ignorado por falta de dados.")
            resultados[label] = {"tendencia": "ERRO", "ema9": None, "ema21": None, "ema50": None}
            confluencia = False
            motivo_rejeicao.append(f"{label}: erro ao obter dados")
            continue

        r = tendencia(closes, label)
        resultados[label] = r
        t = r["tendencia"]
        logger.debug(f"📈 - TF {label}: Tendência {t} (EMA9:{r['ema9']} | EMA21:{r['ema21']} | EMA50:{r['ema50']})")

        if tipo_ordem == "SHORT" and t == "ALTA":
            confluencia = False
            motivo = f"{label} em ALTA (EMA9 > EMA21 > EMA50)"
            logger.warning(f"🚫 - {symbol} SHORT rejeitado: {motivo}")
            motivo_rejeicao.append(motivo)
        elif tipo_ordem == "LONG" and t == "BAIXA":
            confluencia = False
            motivo = f"{label} em BAIXA (EMA9 < EMA21 < EMA50)"
            logger.warning(f"🚫 - {symbol} LONG rejeitado: {motivo}")
            motivo_rejeicao.append(motivo)

    if confluencia:
        logger.info(f"✅ - Confluência confirmada para {symbol} {tipo_ordem}")
    else:
        logger.warning(f"❌ - Confluência NEGADA para {symbol} {tipo_ordem}")

    return {
        "symbol": symbol,
        "tipo_ordem": tipo_ordem,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "timeframes": resultados,
        "confluencia": confluencia,
        "motivo_rejeicao": motivo_rejeicao if not confluencia else [],
        "polymarket": None
    }

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"erro": "uso: analise_tecnica.py SYMBOL TIPO_ORDEM"}))
        sys.exit(1)

    symbol = sys.argv[1]
    tipo_ordem = sys.argv[2].upper()
    resultado = analisar(symbol, tipo_ordem)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))