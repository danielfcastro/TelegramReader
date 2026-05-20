import sys
import json
from integration.BingXBroker import BingXBroker

broker = BingXBroker()
res = broker.obter_ordens_abertas("TRUMPSOL-USDT")
print(json.dumps(res, indent=4))
