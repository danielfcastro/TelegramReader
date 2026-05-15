import json
from integration.BingXBroker import BingXBroker

broker = BingXBroker()
# Vamos tentar buscar ordens abertas para TRUMPSOL-USDT
res = broker._send_request("GET", "/openApi/swap/v2/trade/openOrders", {"symbol": "TRUMPSOL-USDT"})
print(json.dumps(res, indent=2))
