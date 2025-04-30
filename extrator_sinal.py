import re

def extrair_sinal_trade(mensagem):
    try:
        pair_match = re.search(r"(?:🟢|🔴)?([A-Z0-9]+/USDT)", mensagem)
        type_match = re.search(r"(LONG|BUY|SHORT|SELL)", mensagem, re.IGNORECASE)
        entry_match = re.search(r"ENTRY: *[<\[]?([0-9\.]+)-([0-9\.]+)[>\]]?", mensagem)
        sl_match = re.search(r"STOP ?LOSS: *[\[]?([0-9\.]+)[\]]?", mensagem, re.IGNORECASE)
        targets = re.findall(r"\[([0-9\.]+)\]", mensagem)

        if not (pair_match and type_match and entry_match and sl_match):
            return None

        sinal = {
            "pair": pair_match.group(1).upper(),
            "type": type_match.group(1).upper(),
            "entry_low": float(entry_match.group(1)),
            "entry_high": float(entry_match.group(2)),
            "stoploss": float(sl_match.group(1))
        }

        for i, alvo in enumerate(targets[:4], start=1):
            sinal[f"tp{i}"] = float(alvo)

        return sinal
    except Exception:
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
