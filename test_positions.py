import sys
import json
from integration.BingXBroker import BingXBroker

broker = BingXBroker()
res = broker._send_request("GET", "/openApi/swap/v2/user/positions", {})
with open('positions_output.json', 'w') as f:
    json.dump(res, f, indent=4)
