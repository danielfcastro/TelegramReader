import logging
import os
import time

from database.db import (
    break_even_configurado,
    break_even_incrementar_retry,
    break_even_sinal,
    ordem_desabilitar,
    sinal_disparar_trade,
    ordem_incrementar_retry,
    ordem_enviada
)
from utils import ajustar_quantidade
from utils import extrair_limite_usdt

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
            sinais = sinal_disparar_trade()

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
                                ordem_desabilitar(sinal["id"])
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
                        symbol, side, leverage, side_leverage, float(sinal["tp"]), float(sinal["sl"]), quantidade, preco_mercado, sinal["id"]
                    )

                    if sucesso:
                        ordem_enviada(sinal["id"], entry_price, order_id, quantidade)
                    else:
                        if "symbol not exist" in str(info_extra).lower():
                            ordem_desabilitar(sinal["id"])
                        else:
                            codigo = info_extra.get("code", "sem_codigo")
                            mensagem = info_extra.get("msg", "Erro desconhecido")
                            motivo = f"[{codigo}] {mensagem}"
                            logger.error(f"❌ - Falha ao enviar ordens: {motivo} - Dados: {response}")

                            # Se o erro indicar limite de posição, tenta ajustar e reenviar
                            limite_usdt = extrair_limite_usdt(motivo)
                            broker.send_order_with_constraints_adjusted(
                                symbol, side, leverage, side_leverage, float(sinal["tp"]), float(sinal["sl"]),
                                preco_mercado, limite_usdt, sinal["id"])
                            ordem_incrementar_retry(sinal["id"])
            else:
                sinal_be = break_even_sinal()
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
                            break_even_configurado(info["par"])
                        else:
                            break_even_incrementar_retry(info["id"])

            time.sleep(2)

        except KeyboardInterrupt:
            logger.info("🛑 - Executor encerrado pelo usuário.")
            break
        except Exception as e:
            logger.error(f"❌ - Erro geral no executor: {e}")
