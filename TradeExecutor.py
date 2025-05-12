import time
import os
import logging
from database.db import (
    buscar_sinal_execucao,
    marcar_ordem_para_be_executado,
    marcar_ordem_enviada,
    incrementar_retry_be,
    incrementar_retry_order,
    desabilitar_sinal,
    buscar_sinal_para_break_even
)
from utils import ajustar_quantidade

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

def iniciar_executor(broker):
    """
    Inicia o executor principal responsável por:

    - Enviar ordens de trade com base em sinais pendentes.
    - Ativar break even quando atingidas condições de monitoramento.
    - Atualizar o banco de dados conforme o sucesso ou falha das operações.
    - Tratar falhas específicas como símbolo inexistente ou erro de preço de mercado.

    O executor roda em loop contínuo com pausa de 1.2s entre ciclos.

    Args:
        broker (BrokerInterface): Objeto que implementa os métodos de envio de ordens e ajuste de SL.
    """
    logger.info("✅ - Executor iniciado com 1 thread para trade + break even")

    while True:
        try:
            sinais = buscar_sinal_execucao()

            if sinais:
                #sinal já trará a proporção para ser usada no cálculo da quantidade
                saldo = broker.obter_saldo_disponivel()
                symbol = sinais[0]["par"].replace("/", "-").upper()

                try:
                    preco_mercado = broker.obter_preco_mercado(symbol)
                except Exception as e:
                    logger.error(f"❌ - Erro ao obter preço de mercado de {symbol}")
                    if "erro ao obter preço de mercado de" in str(e).lower():
                        for sinal in sinais:
                            if sinal["par"].replace("/", "-").upper() == symbol:
                                desabilitar_sinal(sinal["id"])
                    continue

                for sinal in sinais:
                    tipo_ordem = str(sinal["tipo_ordem"]).upper()
                    symbol = sinal["par"].replace("/", "-").upper()
                    side = "BUY" if tipo_ordem == "LONG" else "SELL"
                    leverage = int(sinal["alavancagem"].replace("X", ""))
                    side_leverage = "BOTH"
                    trade_percentage = float(os.getenv("TRADE_PERCENTAGE", "3"))
                    proporcao = sinal["proporcao"]

                    valor_trade = saldo * (trade_percentage / 100)
                    quantidade = ajustar_quantidade((valor_trade * proporcao) / preco_mercado, step=0.0001)

                    logger.info(f"📦 - Enviando ordem para {sinal['par']}")

                    sucesso, entry_price, order_id, info_extra = broker.enviar_ordem_tp_sl(
                        symbol, side, leverage, side_leverage, float(sinal["tp"]), float(sinal["sl"]), quantidade, preco_mercado
                    )

                    if sucesso:
                        marcar_ordem_enviada(sinal["id"], entry_price, order_id, quantidade)
                    else:
                        if "symbol not exist" in str(info_extra).lower():
                            desabilitar_sinal(sinal["id"])
                        else:
                            incrementar_retry_order(sinal["id"])
            else:
                sinal_be = buscar_sinal_para_break_even()
                _symbol = None
                for info in sinal_be:
                    if info:
                        if _symbol == info["par"].replace("/", "-").upper():
                            continue
                        _symbol = info["par"].replace("/", "-").upper()
                        logger.info(f"⚙️ - Ajustando BE para {_symbol}")
                        sucesso = broker.ajustar_para_break_even(
                            symbol=_symbol,
                            position_side="LONG" if info["tipo_ordem"].upper() == "LONG" else "SHORT",
                            quantity=info["quantidade"],
                            stop_price=info["entry_price"],
                            order_id=info["order_id"]
                        )
                        if sucesso:
                            marcar_ordem_para_be_executado(info["par"])
                        else:
                            incrementar_retry_be(info["id"])

            time.sleep(2)

        except KeyboardInterrupt:
            logger.info("🛑 - Executor encerrado pelo usuário.")
            break
        except Exception as e:
            logger.error(f"❌ - Erro geral no executor: {e}")
