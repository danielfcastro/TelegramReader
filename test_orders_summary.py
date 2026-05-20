import sys
import json
from integration.BingXBroker import BingXBroker

broker = BingXBroker()
res = broker.obter_ordens_abertas("TRUMPSOL-USDT")
data = res.get("data", {}).get("orders", [])
tps = [o for o in data if o["type"] == "TAKE_PROFIT_MARKET"]
sls = [o for o in data if o["type"] == "STOP_MARKET"]
tss = [o for o in data if o["type"] in ["TRAILING_STOP_MARKET", "TRAILING_TP_SL"]]
print(f"Total TPs: {len(tps)}")
print(f"Total SLs: {len(sls)}")
print(f"Total TSs: {len(tss)}")
if len(sls) > 0:
    print(f"SL Price: {sls[0]['stopPrice']}")
for i, tp in enumerate(tps):
    print(f"TP{i+1} Price: {tp['stopPrice']}")
