import queue
import logging
import os
import database

from message.mensagem_sinal import MensagemSinal
from integration.BingXBroker import BingXBroker
from utils import ajustar_quantidade
from log.logger_config import configurar_logging

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
fila_sinal = queue.Queue()
proporcoes = [0.1, 0.2, 0.5, 0.2]
REQUIRED_MARGIN_TYPE = "CROSSED"
configurar_logging()
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
            #Recupera preço de mercado
            preco_mercado = broker.obter_preco_mercado(msg.symbol)
            #Verifica o tipo de margem
            margin_type = broker.verificar_tipo_margem(msg.symbol)
            #Se for diferente de crossed configura para crossed
            if margin_type != REQUIRED_MARGIN_TYPE:
                broker.mudar_tipo_margem(msg.symbol)

            #Recupera saldo disponível
            saldo = broker.obter_saldo_disponivel()
            #Recupera se é BUY ou SELL
            tipo_ordem = msg.tipo_ordem.upper()
            #Recupera o risco do trade na forma de percentagem do saldo
            trade_percentage = float(os.getenv("TRADE_PERCENTAGE", "3"))
            #Calcula o valor monetário da trade
            valor_trade = saldo * (trade_percentage / 100)
            #Calcula a quantidade de moedas para o trade
            quantidade_total = ajustar_quantidade(valor_trade / preco_mercado, step=0.0001)
            #Envia a ordem
            sucesso, order_id, quantidade, average_price, codigo, mensagem_erro = broker.enviar_ordem_tp_sl(msg, quantidade_total)

            if sucesso:
                #Insere a ordem no banco com o id da ordem e o preço de envio
                database.sinal.ordem_inserir(msg.to_dict(), order_id, average_price, quantidade)

                side = "SELL" if tipo_ordem.upper() == "BUY" else "BUY"
                tps = [msg.tp1, msg.tp2, msg.tp3, msg.tp4]

                objetos_tp = []
                for i, proporcao in enumerate(proporcoes):
                    qtd_tp = ajustar_quantidade(quantidade * proporcao, step=0.0001)
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

                database.take_profit.tp_inserir(objetos_tp)
                print(f"✅ Ordem enviada e TPs configurados com sucesso: {msg.symbol}")
            else:
                print(f"❌ Erro ao enviar ordem para {msg.symbol}: {mensagem_erro}")

        except Exception as e:
            print(f"❌ Erro ao processar mensagem de sinal: {e}")
            logger.error(f"❌ - Erro completo: {e}")