import os
import time
import hmac
import json
import requests
import logging
from hashlib import sha256
from dotenv import load_dotenv

from database.db import somar_quantidade_para_be
from integration.BrokerInterface import BrokerInterface

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
        return signature

    def _send_request(self, method, path, params):
        query = self._build_query(params)
        sign = self._get_sign(query)
        url = f"{self.API_URL}{path}?{query}&signature={sign}"
        headers = {
            'X-BX-APIKEY': self.API_KEY
        }
        response = requests.request(method, url, headers=headers)
        return response.json()

    @staticmethod
    def _build_query(params):
        # Sempre adiciona timestamp, mesmo que params esteja vazio
        all_params = dict(params) if params else {}
        all_params["timestamp"] = str(int(time.time() * 1000))

        sorted_params = sorted(all_params.items())
        query = "&".join(f"{k}={v}" for k, v in sorted_params)
        #logger.debug(f"query: {query}")
        return query

    def obter_preco_mercado(self, symbol):
        path = "/openApi/swap/v2/quote/premiumIndex"
        response = self._send_request("GET", path, {"symbol": symbol})
        if response["code"] == 0 and response.get("data"):
            logger.debug(f"preço de mercado: {response['data'].get('markPrice')}")
            return float(response["data"]["markPrice"])
        raise Exception(f"❌ - Erro ao obter preço de mercado de {symbol}")

    def obter_saldo_disponivel(self):
        try:
            path = "/openApi/swap/v3/user/balance"
            params = {}
            response = self._send_request("GET", path, params)
            print("✅ - Resposta da API:", response)

            if response["code"] == 0 and response.get("data"):
                for item in response["data"]:
                    if item["asset"] in ["USDT", "VST"]:
                        logger.debug(f"saldo disponivel: {item['asset']}")
                        return float(item.get("availableMargin", 0.0))
        except Exception as e:
            logger.exception(f"❌ - Exceção ao consular saldo disponível: {e}")
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
            logger.debug("✅ - Leverage configurado:", response)
        except Exception as e:
            logger.exception(f"❌ - Exceção ao ajustar leverage para {symbol}: {e}")

    def enviar_ordem_tp_sl(self, symbol, side, leverage, side_leverage, tp, sl, quantidade, preco_mercado):
        side_leverage = "BOTH"
        logger.debug(f"symbol: {symbol} - side: {side} - leverage: {leverage} - side_leverage: {side_leverage} - tp: {tp} - sl: {sl} - quantidade: {quantidade} - preco_mercado: {preco_mercado}")
        try:
            # Configura o leverage antes de enviar a ordem
            self.set_leverage(symbol=symbol, side=side_leverage, leverage=leverage)

            body = {
                "symbol": symbol,
                "side": side,
                "positionSide": side_leverage,
                "type": "MARKET",
                "quantity": quantidade,
                "stopGuaranteed": "true",
                "takeProfit": json.dumps({
                    "type": "TAKE_PROFIT_MARKET",
                    "quantity": quantidade,
                    "stopPrice": tp,
                    "workingType": "MARK_PRICE"
                }),
                "stopLoss": json.dumps({
                    "type": "STOP_MARKET",
                    "quantity": quantidade,
                    "stopPrice": sl,
                    "workingType": "MARK_PRICE"
                })
            }
            path = "/openApi/swap/v2/trade/order"

            response = self._send_request("POST", path, body)
            logger.debug(f"response: {response} - body: {body} - path: {path} - POST")
            if response["code"] == 0:
                order_id = response["data"]["order"]["orderId"]
                logger.info(f"✅ - Ordens enviadas com sucesso - order_id: {order_id} - preco_mercado: {preco_mercado}")
                return True, preco_mercado, order_id, quantidade
            else:
                codigo = response.get("code", "sem_codigo")
                mensagem = response.get("msg", "Erro desconhecido")
                motivo = f"[{codigo}] {mensagem}"
                logger.error(f"❌ - Falha ao enviar ordens: {motivo} - Dados: {response}")
                return False, None, None, motivo

        except Exception as e:
            print("❌ - Erro ao enviar ordens BingX:", e)
            return False, 0.0, 0

    def cancela_stop_loss(self, symbol):
        try:
            path = "/openApi/swap/v2/trade/allOpenOrders"
            body = {
                "symbol": symbol,
                "type": "STOP_MARKET"
            }
            response = self._send_request("DELETE", path, body)
            logger.debug(f"✅ - Cancelamento de SL: {response} com sucesso")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao cancelar SL para {symbol}: {e}")

    def ajustar_para_break_even(self, symbol, position_side, quantity, stop_price, order_id):
        try:
            cancel = self.cancela_stop_loss(symbol)
            orders = self.get_open_order_info(symbol,order_id)
            side = "SELL" if position_side.upper() == "SHORT" else "BUY"
            position_side = position_side.upper()
            quantidade = somar_quantidade_para_be(symbol.replace("-", "/").upper())
            logger.debug(
                f"🛡️ - Ajustando Stop Loss - symbol: {symbol}, side: {side}, position_side: {position_side}, stop_price: {stop_price}")

            path = "/openApi/swap/v2/trade/order"
            body = {
                "symbol": symbol,
                "side": side,
                "type": "STOP_MARKET",
                "stopPrice": float(orders['data']['order']['avgPrice']),
                "positionSide": "BOTH",
                "quantity": quantidade,
                "recvWindow": "10000"
            }

            headers = {
                "X-BX-APIKEY": self.API_KEY
            }

            response = self._send_request("POST", path, body)
            logger.debug(f"📩 Resposta do SL: {response} - body: {body} - path: {path} - POST")

            if response["code"] == 0:
                logger.info(f"✅ - Stop Loss ajustado com sucesso para {symbol}")
                return True
            else:
                logger.error(f"❌ - Erro ao ajustar SL para {symbol}: {response}")
                return False

        except Exception as e:
            logger.exception(f"❌ - Exceção ao ajustar SL para {symbol}: {e}")
            return False

    def ativar_trailing_stop(self, symbol, order_id, side, quantity, price_rate, position_side):
        try:
            # Cancelar qualquer STOP_MARKET ativo antes de configurar trailing
            logger.debug(f"🧹 Cancelando SL ativo para {symbol} antes do trailing stop")
            self.cancela_stop_loss(symbol)

            # Construção da ordem de trailing stop
            path = "/openApi/swap/v2/trade/order"
            logger.debug(f"🚦 Ativando trailing stop para {symbol} com ordem {order_id}")

            params = {
                "cancelReplaceMode": "ALLOW_FAILURE",
                "cancelOrderId": order_id,
                "cancelRestrictions": "ONLY_NEWS",
                "symbol": symbol,
                "side": side,
                "type": "TRAILING_TP_SL",
                "positionSide": position_side,
                "priceRate": str(price_rate),
                "quantity": quantity
            }

            response = self._send_request("POST", path, params)
            logger.debug(f"✅ - Response do trailing stop: {response}")

            if response["code"] == 0:
                logger.info(f"✅ - Trailing stop ativado com sucesso para {symbol} (order_id: {order_id})")
                return True
            else:
                logger.error(f"❌ - Erro ao ativar trailing stop para {symbol}: {response}")
                return False

        except Exception as e:
            logger.exception(f"❌ - Exceção ao ativar trailing stop para {symbol}: {e}")
            return False

    def get_open_order_info(self, symbol, order_id):
        try:
            path = "/openApi/swap/v2/trade/order"
            body = {
                "symbol": symbol,
                "orderId": order_id
            }
            response = self._send_request("GET", path, body)
            logger.debug(f"✅ - Detalhe de ordem: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao boter detalhe de ordem {symbol}: {e}")