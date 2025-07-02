
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

        :param payload: String de consulta formatada com parâmetros ordenados.
        :return: Assinatura em hexadecimal.
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

        :param method: Método HTTP ('GET', 'POST', etc.).
        :param path: Caminho do endpoint.
        :param params: Parâmetros de requisição.
        :return: Resposta da API.
        """

        query = self._build_query(params)
        sign = self._get_sign(query)
        url = f"{self.API_URL}{path}?{query}&signature={sign}"
        headers = {
            'X-BX-APIKEY': self.API_KEY
        }
        try:
            response = requests.request(method, url, headers=headers)

        except requests.exceptions.ConnectionError as e:
            if "NameResolutionError" in str(e):
                logger.warning("🌐 - Falha de DNS detectada. Aguardando para tentar novamente...")
                time.sleep(10)
                return self._send_request(method, path, params)  # retry simples
            raise

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ - Erro ao enviar requisição para {path}: {e}")
            raise
        return response.json()

    @staticmethod
    def _build_query(params):
        """
        Constrói a string de query com parâmetros ordenados e timestamp.

        :param params: Parâmetros da requisição.
        :return: Query ordenada com timestamp.
        """
        # Sempre adiciona timestamp, mesmo que params esteja vazio
        all_params = dict(params) if params else {}
        all_params["timestamp"] = str(int(time.time() * 1000))

        sorted_params = sorted(all_params.items())
        query = "&".join(f"{k}={v}" for k, v in sorted_params)
        return query

    def obter_preco_mercado(self, symbol):
        """
        Obtém o preço atual de marcação (mark price) para o ativo.

        :param symbol: Par de negociação (ex: "BTC-USDT").
        :return: Preço atual de mercado.
        :raises Exception: Se a resposta da API for inválida.
        """
        path = "/openApi/swap/v2/quote/premiumIndex"
        body = {
            "symbol": symbol
        }
        logger.debug(f"✅️ - Pedido de preço de mercado: path: {path} - body {body}")
        response = self._send_request("GET", path, body)
        logger.debug(f"✅ - Resposta do pedido de preço de mercado: {response}")
        if response["code"] == 0 and response.get("data"):
            return float(response["data"]["markPrice"])
        raise Exception(f"❌ - Erro ao obter preço de mercado de {symbol}")

    def obter_saldo_disponivel(self):
        """
        Consulta o saldo disponível em USDT ou VST.

        :return: Saldo disponível.
        :raises Exception: Se não for possível consultar o saldo.
        """
        try:
            path = "/openApi/swap/v3/user/balance"
            body = {}
            logger.debug(f"✅️ - Pedido de saldo: path: {path} - body {body}")
            response = self._send_request("GET", path, body)
            logger.debug(f"✅ - Resposta do pedido de saldo: {response}")
            if response["code"] == 0 and response.get("data"):
                for item in response["data"]:
                    if item["asset"] in ["USDT", "VST"]:
                        logger.debug(f"🚦 - saldo disponivel: {item['asset']}")
                        return float(item.get("availableMargin", 0.0))
        except Exception as e:
            logger.exception(f"❌ - Exceção ao consular saldo disponível: {e}")
            raise Exception("Não foi possível obter saldo disponível em USDT", "VST.")

    def set_leverage(self, symbol, side, leverage):
        """
        Define a alavancagem desejada para o símbolo.

        :param symbol: Par de ativos.
        :param side: Direção da posição (ex: 'BOTH').
        :param leverage: Valor da alavancagem.
        """

        path = "/openApi/swap/v2/trade/leverage"
        body = {
            "symbol": symbol,
            "side": side,
            "leverage": str(leverage).replace("X", "")
        }

        try:
            logger.debug(f"✅️ - Pedido de envio de alavancagem: path: {path} - body {body}")
            response = self._send_request("POST", path, body)
            logger.debug(f"✅ - Resposta do pedido de alavancagem: {response}")
        except Exception as e:
            logger.exception(f"❌ - Exceção ao ajustar leverage para {symbol}: {e}")

    def enviar_ordem_tp_sl(self, mensagem: MensagemSinal, quantidade):
        """
        Envia uma ordem de mercado com SL embutido para o par especificado.

        Etapas:
        1. Define alavancagem.
        2. Envia ordem com `stopLoss` do tipo STOP_MARKET.
        3. Retorna dados da ordem ou erro.

        :param mensagem: Dados do sinal a ser executado.
        :param quantidade: Quantidade do ativo a negociar.
        :return: Resultado da operação (sucesso, order_id, preço, erros).
        """
        side_leverage = "BOTH"
        logger.debug(f"✅️ - symbol: {mensagem.symbol} - side: {mensagem.tipo_ordem} - leverage: {mensagem.alavancagem} - tp1: {mensagem.tp1} - t2: {mensagem.tp2}  - tp3: {mensagem.tp3}  - tp4: {mensagem.tp4} - sl: {mensagem.sl}")

        try:
            self.set_leverage(symbol=mensagem.symbol, side=side_leverage, leverage=mensagem.alavancagem)
            _tipo_ordem = "SELL" if mensagem.tipo_ordem == "SHORT" else "BUY"
            body = {
                "symbol": mensagem.symbol,
                "side": _tipo_ordem,
                "positionSide": side_leverage,
                "type": "MARKET",
                "quantity": quantidade,
                "stopLoss": json.dumps({
                    "type": "STOP_MARKET",
                    "quantity": quantidade,
                    "stopPrice": mensagem.sl,
                    "workingType": "MARK_PRICE"
                })
            }

            path = "/openApi/swap/v2/trade/order"
            logger.debug(f"✅️ - Pedido de envio de ordem: path: {path} - body {body}")
            response = self._send_request("POST", path, body)
            logger.debug(f"✅ - Resposta do pedido de ordem: {response}")

            codigo = response.get("code", "sem_codigo")
            mensagem_erro = response.get("msg", "Erro desconhecido")
            if codigo == 0:
                order_id = response["data"]["order"]["orderId"]
                average_price = response["data"]["order"]["avgPrice"]
                quantidade = response["data"]["order"]["quantity"]
                logger.info(f"✅ - Ordem enviada com sucesso - order_id: {order_id}")
                retorno =  {
                    "sucesso": True,
                    "order_id": order_id,
                    "quantidade": quantidade,
                    "average_price":average_price,
                    "erro":codigo,
                    "msg":mensagem_erro
                }
                logger.info(f"✅ - Ordem enviada: [{codigo}] {retorno}")
                return retorno
            else:
                mensagem_erro = response.get("msg", "Erro desconhecido")
                retorno = {
                    "sucesso": False,
                    "order_id": 0,
                    "quantidade": 0,
                    "average_price":0,
                    "erro":codigo,
                    "msg":mensagem_erro
                }
                logger.error(f"❌ - Falha ao enviar ordem: [{codigo}] {retorno}")
                return retorno
        except Exception as e:
            logger.exception(f"❌ - Erro ao enviar ordem BingX: {e}")
            return {"sucesso": False, "erro": str(e)}

    def ajustar_stop_loss(self, symbol, position_side, quantity, stop_price, order_id, current_order_side):
        """
        Ajusta o Stop Loss para uma posição específica.
        Se a corretora retornar erro de quantidade, tenta com sugestão do sistema.

        :param symbol: Par de negociação.
        :param position_side: Direção da posição.
        :param quantity: Quantidade a ajustar.
        :param stop_price: Novo preço de SL.
        :param order_id: ID da ordem ativa.
        :param current_order_side: Direção atual da ordem.
        :return: True se SL foi ajustado com sucesso, False caso contrário.
        """
        try:
            ordem = self.get_open_order_info(symbol, order_id)
            if not ordem:
                logger.warning(f"⚠️ - Nenhuma ordem encontrada para {symbol}")
                return {"status": "no_order"}

            path="/openApi/swap/v2/trade/order"
            side = "SELL" if current_order_side == "BUY" else "SELL"
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
                logger.info(f"✅️ - Pedido de envio de SL: path: {path} - body {body}")
                response = self._send_request("POST", path, body)
                logger.info(f"✅ - Resposta do pedido de SL: {response}")
                return response

            self.cancela_ordem_sl(symbol)
            response = enviar_sl(quantity)

            # Verifica sucesso
            if response["code"] == 0:
                logger.info(f"✅ - Stop Loss ajustado com sucesso para {symbol}")
                return True

            # Erro 110424: Tenta ajustar automaticamente
            elif response.get("code") == 110424:
                msg = response.get("msg", "")
                match = re.search(r'available amount of (\d+\.?\d*)', msg)
                if match:
                    nova_quantidade = float(match.group(1))
                    nova_quantidade = round(nova_quantidade, 6)
                    logger.warning(f"⚠️ - Ajustando SL com quantidade reduzida: {nova_quantidade} para {symbol}")
                    response = enviar_sl(nova_quantidade)
                    if response["code"] == 0:
                        logger.info(f"✅ - SL ajustado com nova quantidade para {symbol}")
                        return True
                    else:
                        logger.error(f"❌ - Mesmo após ajuste, falhou SL para {symbol}: {response}")
                        return False
                else:
                    logger.error(f"❌ - Erro 110424 sem número detectável em: {msg}")
                    return False
            else:
                logger.error(f"❌ - Erro ao ajustar SL para {symbol}: {response}")
                return False

        except Exception as e:
            logger.exception(f"❌ - Exceção ao ajustar SL para {symbol}: {e}")

        return False

    def ajustar_take_profit(self, symbol, position_side, quantity, stop_price, order_id, numero):
        """
        Envia ordem de TAKE_PROFIT_MARKET para uma fração da posição.

        :param symbol: Par de negociação.
        :param position_side: Direção da posição.
        :param quantity: Quantidade parcial a fechar.
        :param stop_price: Preço alvo.
        :param order_id: Ordem relacionada.
        :param numero: Número do TP (1 a 4).
        :return: True se a ordem for enviada com sucesso.
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
            logger.debug(f"✅ - Pedido de TP: path: {path} - body {body}")
            response = self._send_request("POST", path, body)
            logger.debug(f"✅ - Resposta do pedido de TP: {response}")

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
        Obtém detalhes da ordem aberta.

        :param symbol: Par de negociação.
        :param order_id: ID da ordem.
        :return: Dados da ordem, se existirem.
        """
        try:
            path = "/openApi/swap/v2/trade/order"
            body = {
                "symbol": symbol,
                "orderId": order_id
            }
            logger.debug(f"✅ - Pedido de detalhe de ordem: path: {path} - body {body}")
            response = self._send_request("GET", path, body)
            logger.debug(f"✅ - Resposta do pedido de detalhe de ordem: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao obter detalhe de ordem {symbol}: {e}")
            return {}

    def fecha_ordem_mercado(self, symbol):
        """
        Fecha todas as posições de mercado abertas para o ativo.

        :param symbol: Par de negociação.
        :return: Resposta da API.
        """
        try:
            path = "/openApi/swap/v2/trade/closeAllPositions"
            body = {
                "symbol": symbol,
                "type": "MARKET"
            }
            logger.debug(f"✅ - Pedido de fechamento de ordem de mercado: path: {path} - body {body}")
            response = self._send_request("POST", path, body)
            logger.debug(f"✅ - Resposta do pedido de fechamento de ordem de mercado: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao fechar ordem {symbol}: {e}")
            return {}

    def cancela_ordem_tp(self, symbol):
        """
        Cancela todas as ordens TAKE_PROFIT_MARKET abertas para o ativo.

        :param symbol: Par de negociação.
        :return: Resposta da API.
        """
        try:
            path = "/openApi/swap/v2/trade/allOpenOrders"
            body = {
                "symbol": symbol,
                "type": "TAKE_PROFIT_MARKET"
            }
            logger.debug(f"✅ - Pedido de cancelamento de ordem de TP: path: {path} - body {body}")
            response = self._send_request("DELETE", path, body)
            logger.debug(f"✅ - Resposta do pedido de cancelamento de ordem de TP: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao cancelar ordem {symbol}: {e}")
            return {}

    def cancela_ordem_sl(self, symbol):
        """
        Cancela todas as ordens STOP_MARKET abertas para o ativo.

        :param symbol: Par de negociação.
        :return: Resposta da API.
        """
        try:
            path = "/openApi/swap/v2/trade/allOpenOrders"
            body = {
                "symbol": symbol,
                "type": "STOP_MARKET"
            }
            logger.debug(f"✅ - Pedido de cancelamento de ordem de SL: path: {path} - body {body}")
            response = self._send_request("DELETE", path, body)
            logger.debug(f"✅ - Resposta do pedido de cancelamento de ordem de SL: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao cancelar ordem {symbol}: {e}")
            return {}

    def verificar_tipo_margem(self, symbol):
        """
        Consulta o tipo de margem (CROSSED ou ISOLATED) do ativo.

        :param symbol: Par de negociação.
        :return: Tipo de margem ou vazio em caso de erro.
        """
        try:
            path = "/openApi/swap/v2/trade/marginType"
            body = {
                "symbol": symbol
            }
            logger.debug(f"✅ - Pedido de verificação de tipo de margem: path: {path} - body {body}")
            response = self._send_request("GET", path, body)
            logger.debug(f"✅ - Resposta do pedido de verificação de tipo de margem: {response}")
            return response["data"]["marginType"]
        except Exception as e:
            logger.exception(f"❌ - Erro {symbol}: {e}")
            return {}

    def mudar_tipo_margem(self, symbol):
        """
        Altera o tipo de margem do ativo para CROSSED.

        :param symbol: Par de negociação.
        :return: Resposta da API.
        """
        try:
            path = "/openApi/swap/v2/trade/marginType"
            body = {
                "symbol": symbol,
                "marginType": "CROSSED"
            }
            logger.debug(f"✅ - Pedido de configuração de tipo de margem: path: {path} - body {body}")
            response = self._send_request("POST", path, body)
            logger.debug(f"✅ - Resposta do pedido de configuração de tipo de margem: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro {symbol}: {e}")
            return {}

    def get_pending_order_info(self, symbol, order_id):
        """
        Obtém detalhes da ordem pendente.

        :param symbol: Par de negociação.
        :param order_id: ID da ordem.
        :return: Dados da ordem, se existirem.
        """
        try:
            path = "/openApi/swap/v2/trade/openOrder"
            body = {
                "symbol": symbol,
                "orderId": order_id
            }
            logger.debug(f"✅ - Pedido de detalhe de ordem pendente: path: {path} - body {body}")
            response = self._send_request("GET", path, body)
            logger.debug(f"✅ - Resposta do pedido de detalhe de ordem pendente: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao obter detalhe de ordem pendente {symbol}: {e}")
            return {}

    def lista_todas_as_ordens(self, symbol, order_id=None):
        """
        Obtém todas as ordens pendentes.
        :param symbol: Par de negociação.
        :param order_id: ID da ordem. Opcional.
        :return: Dados da(s) ordem(ns), se existirem.
        """
        try:
            path = "/openApi/swap/v1/trade/fullOrder"
            body = {"symbol": symbol}
            if order_id is not None:
                body["orderId"] = order_id

            logger.debug(
                f"✅ - Pedido de detalhe de todas as ordens para {symbol} - order_id={order_id}: path: {path} - body {body}")
            response = self._send_request("GET", path, body)
            logger.debug(f"✅ - Resposta do pedido: {response}")
            return response
        except Exception as e:
            logger.exception(f"❌ - Erro ao obter detalhe de ordens: {e}")
            return {}
