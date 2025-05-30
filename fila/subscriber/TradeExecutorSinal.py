import os

import database
import queue

from database.sinal import ordem_inserir
from message.mensagem_sinal import MensagemSinal
from integration.BingXBroker import BingXBroker
from utils import ajustar_quantidade

fila_sinal = queue.Queue()
proporcoes = [0.1, 0.2, 0.5, 0.2]
def consumir_sinais():
    print("🚀 TradeExecutorSinal iniciado.")

    broker = BingXBroker()
    while True:
        mensagem = fila_sinal.get()

        if not isinstance(mensagem, dict):
            print("❌ Mensagem inválida recebida na fila de sinais.")
            continue

        try:
            msg = MensagemSinal(**mensagem)
            preco_mercado = broker.obter_preco_mercado(msg.symbol)
            saldo = broker.obter_saldo_disponivel()
            tipo_ordem = msg.tipo_ordem.upper()
            trade_percentage = float(os.getenv("TRADE_PERCENTAGE", "3"))
            valor_trade = saldo * (trade_percentage / 100)
            quantidade_total = ajustar_quantidade(valor_trade / preco_mercado, step=0.0001)

            resultado, order_id, quantidade_usada = broker.enviar_ordem_tp_sl(msg, quantidade_total)

            if resultado.get("sucesso"):
                ordem_inserir(msg.to_dict(), resultado)

                side = "SELL" if tipo_ordem.upper() == "BUY" else "BUY"
                tps = [msg.tp1, msg.tp2, msg.tp3, msg.tp4]

                objetos_tp = []
                for i, proporcao in enumerate(proporcoes):
                    qtd_tp = ajustar_quantidade(quantidade_total * proporcao, step=0.0001)
                    preco_tp = tps[i]
                    sucesso = broker.ajustar_take_profit(
                        symbol=msg.symbol,
                        position_side=side,
                        quantity=qtd_tp,
                        stop_price=preco_tp,
                        order_id=order_id,
                        numero=i+1
                    )

                    if sucesso:
                        objetos_tp.append({
                            "numero": i + 1,
                            "valor": preco_tp,
                            "quantidade": qtd_tp,
                            "order_id": order_id,
                            "status": 1
                        })
                    else:
                        logger.warning(f"⚠️ - Falha ao configurar TP{i + 1} para {msg.symbol}")

                tp_inserir(objetos_tp)
                print(f"✅ Ordem enviada e TPs configurados com sucesso: {msg.symbol}")
            else:
                print(f"❌ Erro ao enviar ordem para {msg.symbol}: {resultado.get('erro')}")

        except Exception as e:
            print(f"❌ Erro ao processar mensagem de sinal: {e}")
            logger.error(f"❌ - Erro completo: {e}")