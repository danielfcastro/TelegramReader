from datetime import datetime
from utils import extrair_sinal_trade
from database.db import inserir_sinal_com_multiplos_tps

mensagem = """
🔴[STO/USDT](https://bingx.com/invite/N51SUM) **SHORT** (sell)
Margin: Cross, 20X
**ENTRY:** <0.19697-0.19895>
———
🎯**TARGETS:**
**1.** [`0.19598`] **2.** [`0.19400`]
**3.** [`0.19202`] **4.** [`0.18806`]
———
❌️**STOPLOSS:** [`0.21776`]
"""

sinal = extrair_sinal_trade(mensagem)
print(sinal)
if sinal:
    print("✅ Inserindo sinal no banco de dados...")
    inserir_sinal_com_multiplos_tps(sinal)
else:
    print("❌ Erro ao extrair sinal da mensagem.")
