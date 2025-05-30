import queue

from database.stop_loss import stop_loss_updatee, stop_loss_soma_quantidade
from database.take_profit import tp_ordem_id_mais_nova, tp_atualizar
from message.mensagem_tp import MensagemTP
from integration.BingXBroker import BingXBroker
import database.db

fila_tp = queue.Queue()  # Essa fila será populada pelo TelegramReader

def consumir_monitoramentos():
    print("📡 TradeExecutorTP iniciado.")
    broker = BingXBroker()

    while True:
        mensagem = fila_tp.get()

        if not isinstance(mensagem, dict):
            logger.warning("❌ Mensagem inválida recebida na fila TP.")
            continue

        try:
            msg = MensagemTP(**mensagem)
            symbol = msg.symbol
            numero_tp = int(msg.tp_monitorado)

            # Enriquecer a mensagem com order_id mais recente
            order_id = tp_ordem_id_mais_nova(symbol)
            if not order_id:
                logger.warning(f"⚠️ Nenhuma ordem executada encontrada para {symbol}")
                continue

            msg.order_id = order_id

            # Atualiza status do TP no banco
            tp_atualizar(order_id=msg.order_id, numero_tp=msg.numero_tp, novo_status=3)

            # Buscar informações da ordem principal
            response = broker.get_open_order_info(symbol=symbol, order_id=order_id)

            if not response:
                logger.warning(f"⚠️ - Nenhuma ordem encontrada para {symbol}")
                continue

            entry_price = response["data"]["order"]["avgPrice"]
            commission = response["data"]["order"]["commission"]
            order_id = response["data"]["order"]["orderId"]
            current_stop_price = response["data"]["order"]["stopLoss"]["stopPrice"]
            # Se TP2, atualiza o SL para ser o entry_price
            if numero_tp == 2:
                stop_loss_update(symbol, entry_price)

            # Decide o novo stop_price com base no TP monitorado
            stop_price = current_stop_price if numero_tp == 1 else entry_price

            # Lógica para ajustar Stop Loss após TP
            if numero_tp <4:
                quantidade = stop_loss_soma_quantidade(symbol)
                sucesso = broker.ajustar_stop_loss(
                    symbol=symbol,
                    position_side="BOTH",
                    quantity=quantidade,
                    stop_price=stop_price,
                    order_id=order_id
                )
                if sucesso:
                    tp_atualizar(order_id=order_id, numero_tp=numero_tp, novo_status=3)
            else:
                response = broker.get_open_order_info(symbol=symbol, order_id=order_id)
                tp_atualizar(order_id=order_id, numero_tp=4, novo_status=3)
                if not response:
                    logger.warning(f"⚠️ - Nenhuma ordem encontrada para {symbol}")
                    continue
                broker.fecha_ordem_mercado(symbol=symbol)
                broker.cancela_ordem_tp(symbol=symbol)
                broker.cancela_ordem_sl(symbol=symbol)

            logger.info(f"✅ TP{numero_tp} processado com sucesso para {symbol}.")

        except Exception as e:
            logger.exception(f"❌ Erro ao processar TP para {mensagem}: {e}")
