import os
import time
import hmac
import json
import requests
import logging
from hashlib import sha256
from dotenv import load_dotenv

from integration.BrokerInterface import BrokerInterface
from utils import ajustar_quantidade

load_dotenv()

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

class BingXBroker(BrokerInterface):
    def __init__(self):
        self.API_URL = os.getenv("broker_api_url")
        self.API_KEY = os.getenv("broker_api_key")
        self.SECRET_KEY = os.getenv("broker_api_secret")

    def _get_sign(self, payload):
        signature = hmac.new(
            self.SECRET_KEY.encode("utf-8"),
            payload.encode("utf-8"),
            digestmod=sha256
        ).hexdigest()
        logger.debug(f"signature: {signature}")
        return signature

    def _send_request(self, method, path, params):
        query = self._build_query(params)
        sign = self._get_sign(query)
        url = f"{self.API_URL}{path}?{query}&signature={sign}"
        headers = {
            'X-BX-APIKEY': self.API_KEY
        }
        response = requests.request(method, url, headers=headers)
        logger.debug(f"response: {response.json()}")
        return response.json()

    def _build_query(self, params):
        # Sempre adiciona timestamp, mesmo que params esteja vazio
        all_params = dict(params) if params else {}
        all_params["timestamp"] = str(int(time.time() * 1000))

        sorted_params = sorted(all_params.items())
        query = "&".join(f"{k}={v}" for k, v in sorted_params)
        logger.debug(f"query: {query}")
        return query

    def obter_preco_mercado(self, symbol):
        path = "/openApi/swap/v2/quote/premiumIndex"
        response = self._send_request("GET", path, {"symbol": symbol})
        if response["code"] == 0:
            logger.debug(f"obter premium index: {response['data']['premiumIndex']}")
            return float(response["data"]["markPrice"])
        raise Exception(f"❌ Erro ao obter preço de mercado de {symbol}")

    def obter_saldo_disponivel(self):
        try:
            path = "/openApi/swap/v3/user/balance"
            params = {}
            response = self._send_request("GET", path, params)
            print("Resposta da API:", response)

            if response["code"] == 0 and response.get("data"):
                for item in response["data"]:
                    if item["asset"] in ["USDT", "VST"]:
                        logger.debug(f"obter saldo disponivel: {item['asset']}")
                        return float(item.get("availableMargin", 0.0))
        except Exception as e:
            print("Erro ao consultar saldo disponível:", e)
        raise Exception("Não foi possível obter saldo disponível em USDT.")

    def set_leverage(self, symbol, side, leverage):
        path = "/openApi/swap/v2/trade/leverage"
        params = {
            "symbol": symbol,
            "side": side,
            "leverage": str(leverage)
        }
        query = self._build_query(params)
        sign = self._get_sign(query)
        url = f"{self.API_URL}{path}?{query}&signature={sign}"

        try:
            response = requests.post(url, headers={'X-BX-APIKEY': self.API_KEY}).json()
            logger.debug("🪙 Leverage configurado:", response)
        except Exception as e:
            print("Erro ao configurar leverage:", e)

    def enviar_ordem_tp_sl(self, sinal):
        symbol = sinal["par"].replace("/", "-").upper()
        side = "BUY" if sinal["tipo_ordem"].upper() == "LONG" else "SELL"
        side_leverage = "LONG" if side == "BUY" else "SHORT"
        leverage = int(sinal["alavancagem"].replace("X", ""))
        logger.debug(f"symbol: {symbol} - side: {side} - leverage: {leverage} - side_leverage: {side_leverage}")
        try:
            # Configura o leverage antes de enviar a ordem
            self.set_leverage(symbol=symbol, side=side_leverage, leverage=leverage)
            
            saldo = self.obter_saldo_disponivel()
            preco_mercado = self.obter_preco_mercado(symbol)
            valor_trade = saldo * float(os.getenv("TRADE_PERCENTAGE", "3")) / 100
            quantidade_total = valor_trade / preco_mercado
            logger.debug(f"saldo: {saldo} - preco_mercado: {preco_mercado} - valor_tade: {valor_trade} - quantidade total: {quantidade_total}")

            proporcoes = [0.1, 0.2, 0.5, 0.1]
            quantidades = [ajustar_quantidade(quantidade_total * p, step=0.0001) for p in proporcoes]
            preco_tp = float(sinal["tp"])
            preco_sl = float(sinal["sl"])

            logger.debug(f"quantidades: {quantidades} - preco_tp: {preco_tp} - preco_sl: {preco_sl}")
            ordens = []
            for q in quantidades:
                ordem = {
                    "symbol": symbol,
                    "side": side,
                    "positionSide": side_leverage,
                    "type": "MARKET",
                    "quantity": q,
                    "takeProfit": json.dumps({
                        "type": "TAKE_PROFIT_MARKET",
                        "quantity": q,
                        "stopPrice": preco_tp,
                        "workingType": "MARK_PRICE"
                    }),
                    "stopLoss": json.dumps({
                        "type": "STOP_MARKET",
                        "quantity": q,
                        "stopPrice": preco_sl,
                        "workingType": "MARK_PRICE"
                    })
                }
                ordens.append(ordem)

            path = "/openApi/swap/v2/trade/order"
            for body in ordens:
                response = self._send_request("POST", path, body)
                logger.debug(f"response: {response} - body: {body} - path: {path} - POST")
                time.sleep(5)

            if response["code"] == 0 and "orders" in response["data"]:
                order_id = response["data"]["orders"][0]["orderId"]
                logger.info(f"Ordens enviadas com sucesso - order_id: {order_id} - preco_mercado: {preco_mercado}")
                return True, preco_mercado, order_id
            else:
                logger.error(f"⚠️ Falha ao enviar ordens: {response}")
                return False, 0.0, 0
        except Exception as e:
            print("❌ Erro ao enviar ordens BingX:", e)
            return False, 0.0, 0

    def ajustar_para_break_even(self, id, order_id, entry_price, tipo_ordem, par):

        try:
            symbol = par.replace("/", "-").upper()
            side = "BUY" if tipo_ordem.upper() == "LONG" else "SELL"
            position_side = "LONG" if tipo_ordem.upper() == "LONG" else "SHORT"
            logger.debug(f"symbol: {symbol} - side: {side} - positionSide: {position_side}")
            body = {
                "symbol": symbol,
                "side": side,
                "positionSide": position_side,
                "type": "MARKET",
                "clientOrderId": order_id,
                "stopLoss": json.dumps({
                    "type": "STOP_MARKET",
                    "stopPrice": entry_price,
                    "workingType": "MARK_PRICE"
                })
            }
            logger.debug(f"body: {body}")

            path = "/openApi/swap/v2/trade/order"
            response = self._send_request("POST", path, {}, body)

            if response["code"] == 0:
                logger.info(f"🟢 Break Even ajustado para {par}")
                return True
            else:
                logger.error(f"❌ Erro ao ajustar BE para {par}: {response}")
                return False

        except Exception as e:
            print(f"❌ Erro no ajuste de break even para {par}:", e)
            return False

