from utils import extrair_mensagem_monitoramento
from database.db import buscar_info_apos_sinal_de_monitoramento, ativar_break_even

mensagem = """
💸STO/USDT
Price 0.19395
**Profit: > 40%**
✅ TARGET #2 DONE
🕒Spent: 0d:00h:16m
———
__*Fix another 20% profit
*Move SL to breakeven price__
"""

monitoramento = extrair_mensagem_monitoramento(mensagem)

if monitoramento:
    if monitoramento["tp"] == "TP2":
        print(f"📡 Monitoramento TP2 detectado: {monitoramento['pair']}")
        info = buscar_info_apos_sinal_de_monitoramento(monitoramento["pair"])
        if info:
            print(f"🟢 Ativando BE para ID {info['id']} / par {monitoramento['pair']}")
            ativar_break_even(info["id"])
        else:
            print("❌ Nenhuma ordem enviada encontrada para este par.")
    else:
        print("ℹ️ TP informado não é TP2. Ignorado.")
else:
    print("❌ Erro ao extrair monitoramento da mensagem.")
