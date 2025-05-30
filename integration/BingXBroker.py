import hmac
import json
import logging
import os
import time
import re
from abc import ABC

from hashlib import sha256

import requests
from dotenv import load_dotenv

from integration.BrokerInterface import BrokerInterface
from message.mensagem_sinal import MensagemSinal

load_dotenv()

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

class BingXBroker(BrokerInterface, ABC):
    def __init__(self):
        """
        Inicializa o broker da BingX carregando as credenciais da API do ambiente.
        """
        self.API_URL = os.getenv("broker_api_url")
        self.API_KEY = os.getenv("broker_api_key")
        self.SECRET_KEY = os.getenv("broker_api_secret")

    def _get_sign(self, payload):
        """
        Gera a assinatura HMAC SHA256 para autenticar requisições.

        Args:
            payload (str): String de consulta formatada com parâmetros ordenados.

        Returns:
            str: Assinatura em hexadecimal.
        """
        signature = hmac.new(
            self.SECRET_KEY.encode("utf-8"),
            payload.encode("utf-8"),
            digestmod=sha256
        ).hexdigest()
        return signature

    def _send_request(self, method, path, params):
        """
        Envia uma requisição autenticada para a API da BingX.

        Args:
            method (str): Método HTTP (ex: 'GET', 'POST').
            path (str): Caminho do endpoint da API.
            params (dict): Parâmetros da requisição (corpo ou query).

        Returns:
            dict: Resposta da API convertida em JSON.
        """

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
        """
        Constrói a string de query com os parâmetros ordenados e adiciona timestamp.

        Args:
            params (dict): Dicionário com os parâmetros da requisição.

        Returns:
            str: String de query formatada para autenticação.
        """
        # Sempre adiciona timestamp, mesmo que params esteja vazio
        all_params = dict(params) if params else {}
        all_params["timestamp"] = str(int(time.time() * 1000))

        sorted_params = sorted(all_params.items())
        query = "&".join(f"{k}={v}" for k, v in sorted_params)
        #logger.debug(f"query: {query}")
        return query

    def obter_preco_mercado(self, symbol):
        """
        Obtém o preço de marcação (mark price) do ativo fornecido.

        Args:
            symbol (str): Par de negociação (ex: "BTC-USDT").

        Returns:
            float: Preço atual de marcação.

        Raises:
            Exception: Se a API falhar ou não retornar dados.
        """
        path = "/openApi/swap/v2/quote/premiumIndex"
        response = self._send_request("GET", path, {"symbol": symbol})
        if response["code"] == 0 and response.get("data"):
            logger.debug(f"preço de mercado: {response['data'].get('markPrice')}")
            return float(response["data"]["markPrice"])
        raise Exception(f"❌ - Erro ao obter preço de mercado de {symbol}")

    def obter_saldo_disponivel(self):
        """
        Consulta o saldo disponível em USDT ou VST na conta do usuário.

        Returns:
            float: Valor de saldo disponível.

        Raises:
            Exception: Se a API falhar ou não houver saldo elegível.
        """
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
        """
        Configura a alavancagem para um determinado par na corretora BingX.

        Args:
            symbol (str): Par de ativos (ex: 'BTC-USDT').
            side (str): Direção da posição ('LONG', 'SHORT', 'BOTH').
            leverage (int | str): Alavancagem desejada.
        """

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

    def enviar_ordem_tp_sl(self, mensagem: MensagemSinal, quantidade):
        side_leverage = "BOTH"
        logger.debug(f"symbol: {mensagem.symbol} - side: {mensagem.tipo_ordem} - leverage: {mensagem.alavancagem} - tp1: {mensagem.tp1} - t2: {mensagem.tp2}  - tp3: {mensagem.tp3}  - tp4: {mensagem.tp4} - sl: {mensagem.sl}")

        try:
            self.set_leverage(symbol=mensagem.symbol, side=side_leverage, leverage=mensagem.alavancagem)

            body = {
                "symbol": mensagem.symbol,
                "side": mensagem.tipo_ordem,
                "positionSide": side_leverage,
                "type": "MARKET",
                "quantity": quantidade,
                "stopGuaranteed": "true",
                "stopLoss": json.dumps({
                    "type": "STOP_MARKET",
                    "quantity": quantidade,
                    "stopPrice": mensagem.sl,
                    "workingType": "MARK_PRICE"
                })
            }

            path = "/openApi/swap/v2/trade/order"
            response = self._send_request("POST", path, body)

            logger.debug(f"response: {response} - body: {body} - path: {path} - POST")
            codigo = response.get("code", "sem_codigo")
            if codigo == 0:
                order_id = response["data"]["order"]["orderId"]
                logger.info(f"✅ - Ordem enviada com sucesso - order_id: {order_id}")
                return {"sucesso": True, "order_id": order_id, "quantidade": quantidade}
            else:
                mensagem_erro = response.get("msg", "Erro desconhecido")
                logger.error(f"❌ - Falha ao enviar ordem: [{codigo}] {mensagem_erro}")
                return {"sucesso": False, "erro": f"[{codigo}] {mensagem_erro}"}
        except Exception as e:
            logger.exception(f"❌ - Erro ao enviar ordem BingX: {e}")
            return {"sucesso": False, "erro": str(e)}

    def cancela_stop_loss(self, symbol):
        """
        Cancela todas as ordens do tipo STOP_MARKET abertas para um ativo.

        Args:
            symbol (str): Símbolo do par de ativos.

        Returns:
            dict: Resposta da API.
        """
        try:
            path = "/openApi/swap/v2/trade/allOpenOrders"
            body = {
                "symbol": symbol,
                "type": "STOP_MARKET"
            }
            logger.debug(f"✅ - Cancelamento de SL: path: {path} - body {body}")
            response = self._send_request("DELETE", path, body)
            logger.debug(f"✅ - Cancelamento de SL: response: {response} com sucesso")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao cancelar SL para {symbol}: {e}")
            return {}

    def ajustar_stop_loss(self, symbol, position_side, quantity, stop_price, order_id):
        """
        Ajusta o Stop Loss de uma posição para o ponto de Break Even (sem lucro ou prejuízo).
        Tenta novamente com a quantidade sugerida pela BingX se a original for rejeitada.

        Returns:
            bool: True se o SL foi ajustado com sucesso.
        """
        try:
            path="/openApi/swap/v2/trade/order"
            def enviar_sl(qtd):
                body = {
                    "symbol": symbol,
                    "side": side,
                    "type": "STOP_MARKET",
                    "stopPrice": stop_price,
                    "positionSide": "BOTH",
                    "quantity": qtd,
                    "orderId": order_id
                }
                return self._send_request("POST", path, body)

            ordem = self.get_open_order_info(symbol, order_id)
            if not ordem:
                logger.warning(f"⚠️ - Nenhuma ordem encontrada para {symbol}")
                return {"status": "no_order"}

            self.cancela_stop_loss(symbol)


            logger.debug(
                f"🛡️ - Tentando SL - symbol: {symbol}, side: {side}, position_side: {side}, stop_price: {stop_price_final}, quantidade: {quantity}")
            response = enviar_sl(quantity)

            # Verifica sucesso
            if response["code"] == 0:
                logger.info(f"✅ - Stop Loss ajustado com sucesso para {symbol}")
                return True

            # Erro 110424: Tenta ajustar automaticamente
            if response.get("code") == 110424:
                msg = response.get("msg", "")
                match = re.search(r'available amount of (\d+\.?\d*)', msg)
                if match:
                    nova_quantidade = float(match.group(1))
                    nova_quantidade = round(nova_quantidade, 6)
                    logger.warning(f"⚠️ - Ajustando SL com quantidade reduzida: {nova_quantidade} para {symbol}")
                    response2 = enviar_sl(nova_quantidade)
                    if response2["code"] == 0:
                        logger.info(f"✅ - SL ajustado com nova quantidade para {symbol}")
                        return True
                    else:
                        logger.error(f"❌ - Mesmo após ajuste, falhou SL para {symbol}: {response2}")
                else:
                    logger.error(f"❌ - Erro 110424 sem número detectável em: {msg}")
            else:
                logger.error(f"❌ - Erro ao ajustar SL para {symbol}: {response}")

        except Exception as e:
            logger.exception(f"❌ - Exceção ao ajustar SL para {symbol}: {e}")

        return False

    def ajustar_take_profit(self, symbol, position_side, quantity, stop_price, order_id, numero):
        """
        Cria uma ordem de Take Profit para uma fração da posição.

        Args:
            :param numero:
            :param order_id:
            :param symbol: string - Par de trading (ex: "BCH-USDT").
            :param position_side: string - Direção da posição ('LONG' ou 'SHORT').
            :param quantity: float - Quantidade da fração.
            :param stop_price: float - Preço alvo do TP.

        Returns:
            bool: True se a ordem foi enviada com sucesso.
        """
        try:
            logger.debug(f"🎯 - Pedido para configurar TP={numero}: symbol={symbol} | side={position_side} | quantity={quantity} | stop_price={stop_price} | order_id={order_id}")
            path = "/openApi/swap/v2/trade/order"
            body = {
                "symbol": symbol,
                "positionSide": "BOTH",
                "side": position_side,
                "type":"TAKE_PROFIT_MARKET",
                "stopPrice": round(stop_price, 6),
                "quantity": round(quantity, 6),
                "workingType": "MARK_PRICE",
                "orderId": order_id
            }
            logger.debug(f"🎯 - body={body} - path={path}")
            response = self._send_request("POST", path, body)
            logger.debug(f"📩 Resposta para TP{numero}: {response} - body: {body}")

            if response["code"] == 0:
                logger.info(f"✅ - TP{numero} configurado com sucesso para {symbol} a {stop_price}")
                return True
            else:
                logger.warning(f"⚠️ - Falha ao configurar TP{numero} para {symbol}: {response}")
                return False

        except Exception as e:
            logger.exception(f"❌ - Exceção ao configurar TP{numero} para {symbol}: {e}")
            return False

    def get_open_order_info(self, symbol, order_id):
        """
        Obtém informações de uma ordem aberta.

        Args:
            symbol (str): Símbolo do par de ativos.
            order_id (str): ID da ordem.

        Returns:
            dict: Dados detalhados da ordem retornados pela API.
        """
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
            return {}

    def fecha_ordem_mercado(self, symbol):
        try:
            path = "/openApi/swap/v2/trade/closeAllPositions"
            body = {
                "symbol": symbol,
                "type": "MARKET"
            }
            logger.debug(f"✅ - Pedido de fechamento de ordem de mercado: body: {body}")
            response = self._send_request("POST ", path, body)
            logger.debug(f"✅ - Resposta do pedido de fechamento de ordem de mercado: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao fechar ordem {symbol}: {e}")
            return {}

    def cancela_ordem_tp(self, symbol):
        try:
            path = "/openApi/swap/v2/trade/allOpenOrders"
            body = {
                "symbol": symbol,
                "type": "TAKE_PROFIT_MARKET"
            }
            logger.debug(f"✅ - Pedido de cancelamento de ordem de TP: body: {body}")
            response = self._send_request("DELETE", path, body)
            logger.debug(f"✅ - Resposta do pedido de cancelamento de ordem de TP: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao boter detalhe de ordem {symbol}: {e}")
            return {}

    def cancela_ordem_sl(self, symbol):
        try:
            path = "/openApi/swap/v2/trade/allOpenOrders"
            body = {
                "symbol": symbol,
                "type": "STOP_MARKET"
            }
            logger.debug(f"✅ - Pedido de cancelamento de ordem de SL: body: {body}")
            response = self._send_request("DELETE", path, body)
            logger.debug(f"✅ - Resposta do pedido de cancelamento de ordem de SL: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao boter detalhe de ordem {symbol}: {e}")
            return {}

    def verificar_tipo_margem(self, symbol):
        try:
            path = "/openApi/swap/v2/trade/marginType"
            body = {
                "symbol": symbol
            }
            logger.debug(f"✅ - Pedido de verificação de tipo de margem: body: {body}")
            response = self._send_request("GET ", path, body)
            logger.debug(f"✅ - Resposta do pedido de verificação de tipo de margem: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro {symbol}: {e}")
            return {}

    def mudar_tipo_margem(self, symbol):
        try:
            path = "/openApi/swap/v2/trade/marginType"
            body = {
                "symbol": symbol,
                "marginType": "CROSSED"
            }
            logger.debug(f"✅ - Pedido de configuração de tipo de margem: body: {body}")
            response = self._send_request("POST ", path, body)
            logger.debug(f"✅ - Resposta do pedido de configuração de tipo de margem: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro {symbol}: {e}")
            return {}
