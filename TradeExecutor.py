import time
import os
from types import NoneType
import logging
from database.db import (
    buscar_sinal_execucao,
    buscar_sinal_para_be,
    marcar_ordem_para_be_executado,
    marcar_ordem_enviada,
    incrementar_retry_be,
    incrementar_retry_order,
    atualizar_quantidades,
    desabilitar_sinal
)
from utils import ajustar_quantidade

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

proporcoes = [0.1, 0.2, 0.5, 0.2]

def iniciar_executor(broker):
    logger.info("✅ - Executor iniciado com 1 thread para trade + break even")

    while True:
        try:
            sinais = buscar_sinal_execucao()
            time.sleep(2)

            if sinais:
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

                trade_percentage = float(os.getenv("TRADE_PERCENTAGE", "3"))
                valor_trade = saldo * (trade_percentage / 100)

                quantidades = [
                    ajustar_quantidade((valor_trade * p) / preco_mercado, step=0.0001)
                    for p in proporcoes
                ]

                lista_id_quantidade = [
                    (sinal["id"], quantidade)
                    for sinal, quantidade in zip(sinais, quantidades)
                ]
                atualizar_quantidades(lista_id_quantidade)

                for sinal, quantidade in zip(sinais, quantidades):
                    symbol = sinal["par"].replace("/", "-").upper()
                    side = "BUY" if sinal["tipo_ordem"].upper() == "LONG" else "SELL"
                    leverage = int(sinal["alavancagem"].replace("X", ""))
                    side_leverage = "BOTH"

                    logger.info(f"📦 - Enviando ordem para {sinal['par']}")

                    sucesso, entry_price, order_id, info_extra = broker.enviar_ordem_tp_sl(
                        symbol, side, leverage, side_leverage, float(sinal["tp"]), float(sinal["sl"]), quantidade, preco_mercado
                    )

                    if sucesso:
                        marcar_ordem_enviada(sinal["id"], entry_price, order_id, quantidade)
                    else:
                        logger.warning(f"⚠️ - Falha ao enviar ordem para {sinal['par']} com quantidade {quantidade}. Motivo: {info_extra}")
                        if "symbol not exist" in str(info_extra).lower():
                            desabilitar_sinal(sinal["id"])
                        else:
                            incrementar_retry_order(sinal["id"])

            else:
                sinal_be = buscar_sinal_para_be()
                for info in sinal_be:
                    if info:
                        #(self, symbol, position_side, quantity, stop_price)
                        logger.info("⚙️ - Ajustando BE para {info['par']}")
                        sucesso = broker.ajustar_para_break_even(
                            symbol=info["par"].replace("/", "-").upper(),
                            position_side="LONG" if info["tipo_ordem"].upper() == "LONG" else "SHORT",
                            quantity=info["quantidade"],
                            stop_price=info["entry_price"],
                            order_id=info["order_id"]
                        )
                        if sucesso:
                            marcar_ordem_para_be_executado(info["par"], info["order_id"])
                        else:
                            incrementar_retry_be(info["id"])

            time.sleep(2)

        except KeyboardInterrupt:
            logger.info("🛑 - Executor encerrado pelo usuário.")
            break
        except Exception as e:
            logger.error(f"❌ - Erro geral no executor: {e}")
