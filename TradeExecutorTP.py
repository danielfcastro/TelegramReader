import logging
import os
import time

from persistqueue import SQLiteQueue

import database
from persistqueue.exceptions import Empty

from log.logger_config import configurar_logging
from message.mensagem_tp import MensagemTP
from integration.BingXBroker import BingXBroker
mensagem = None
fila = SQLiteQueue(os.path.join("fila", "monitoramentos"), auto_commit=False)
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
configurar_logging()

def consumir_monitoramentos():
    """
    Função principal responsável por consumir e processar mensagens da fila de monitoramento de Take Profits (TPs).

    Etapas principais:
    1. Inicializa o broker (BingXBroker).
    2. Entra em loop infinito para consumir a fila `monitoramentos`.
    3. Para cada item na fila:
       - Verifica se é um dicionário válido.
       - Converte para objeto `MensagemTP`.
       - Extrai o símbolo e o número do TP.
       - Busca a `order_id` mais recente no banco relacionada ao símbolo.
           - Se não encontrar, remove a mensagem da fila e segue.
       - Atualiza o status do TP no banco para "em execução" (status 3).
       - Recupera a ordem aberta na corretora.
           - Se não encontrar, remove a mensagem da fila e segue.
       - Extrai dados relevantes da ordem: preço de entrada, comissão, SL atual, lado da ordem.
       - Atualiza o status do TP para "concluído" (status 2).
       - Se for TP2, ajusta o SL para o `entry_price`.
       - Para TP1 a TP3:
           - Soma a quantidade restante de contratos.
           - Ajusta o SL na corretora.
           - Se falhar, desfaz o update do status do TP.
       - Para TP4:
           - Atualiza o status do TP para 2.
           - Encerra a ordem no mercado e cancela ordens TP/SL.
       - Marca a tarefa como concluída na fila.
    4. Em caso de erro de fila vazia (`Empty`), aguarda 2 segundos.
    5. Em qualquer outro erro, registra no log.
    6. Finaliza graciosamente em `KeyboardInterrupt`.
    """
    logger.info(f"✅ - TradeExecutorTP iniciado.")
    broker = BingXBroker()
    logger.debug(f"📦 - Tamanho inicial da fila TP: {fila.qsize()}")
    try:
        while True:
            try:
                #Recupera a mensagem da fila
                mensagem = fila.get(timeout=3)

                #Verifica se está com tipo correto e se não tiver remove da fila e retorna pra próxima iteração
                if not isinstance(mensagem, dict):
                    logger.warning(f"⚠️ -Mensagem inválida recebida na fila TP.")
                    fila.task_done()
                    continue

                #Converte a mensagem no objeto python
                msg = MensagemTP(**mensagem)
                #Recupero o símbolo ligado a mensagem
                symbol = msg.symbol
                #Recupero o Take Profit relacionado a mensagem
                numero_tp = int(msg.tp.replace("TP", ""))

                # Enriquecer a mensagem com order_id mais recente se existir.  Se não achar deleta a mensagem e retorna pra próxima iteração
                order_id = database.take_profit.tp_ordem_id_mais_nova(symbol)
                if order_id == 0:
                    logger.info(f"⚠️ - Nenhuma ordem executada registrada no banco para {symbol}")
                    fila.task_done()
                    continue

                #Atribui order_id a mensagem
                msg.order_id = order_id
                logger.debug(f"📦 - Mensagem: {msg}")

                # Atualiza status do TP no banco
                database.take_profit.tp_atualizar(order_id=msg.order_id, numero_tp=msg.tp, novo_status=3)

                # Buscar informações da ordem principal
                response = broker.get_open_order_info(symbol=symbol, order_id=order_id)

                if not response:
                    logger.warning(f"⚠️ - Nenhuma ordem encontrada na corretora para {symbol}")
                    fila.task_done()
                    continue

                #Recupera o preço de entrada da ordem para futuro uso na mudança de Stop Loss
                entry_price = response["data"]["order"]["avgPrice"]
                # Recupera o valor de comissão da ordem para futuro uso na mudança de Stop Loss
                commission = response["data"]["order"]["commission"]
                # Recupera o valor de order_id da ordem para futuro uso na mudança de Stop Loss
                order_id = response["data"]["order"]["orderId"]
                # Recupera o SL atual da ordem para futuro uso na mudança de Stop Loss
                current_stop_price = response["data"]["order"]["stopLoss"]["stopPrice"]
                # Recupera o lado da ordem (BUY, SELL) da ordem para futuro uso na mudança de Stop Loss
                current_order_side = response["data"]["order"]["stopLoss"]["side"]
                #Atualiza no banco o status do TP
                database.take_profit.tp_atualizar(order_id=order_id, numero_tp=numero_tp, novo_status=2)
                # Se TP2, atualiza o SL para ser o entry_price
                if numero_tp == 2:
                    database.stop_loss.stop_loss_update(symbol, entry_price)

                # Decide o novo stop_price com base no TP monitorado
                stop_price = current_stop_price if numero_tp == 1 else entry_price

                # Lógica para ajustar Stop Loss após TP
                if numero_tp <4:
                    #Soma as quantidades remanescentes dos TPS ainda não concluídos
                    quantidade = database.stop_loss.stop_loss_soma_quantidade(order_id)
                    #Chama broker pra ajustar stop loss
                    sucesso = broker.ajustar_stop_loss(
                        symbol=symbol,
                        position_side="BOTH",
                        quantity=quantidade,
                        stop_price=stop_price,
                        order_id=order_id,
                        current_order_side=current_order_side
                    )
                    #SXe não deu certo a chamada desfaz o update passando o status anterior
                    if not sucesso:
                        database.take_profit.tp_atualizar(order_id=order_id, numero_tp=numero_tp, novo_status=1)
                else:
                    database.take_profit.tp_atualizar(order_id=order_id, numero_tp=4, novo_status=2)
                    time.sleep(1.5)
                    broker.fecha_ordem_mercado(symbol=symbol)
                    broker.cancela_ordem_tp(symbol=symbol)
                    broker.cancela_ordem_sl(symbol=symbol)
                    fila.task_done()
                logger.info(f"✅ - TP{numero_tp} processado com sucesso para {symbol}.")
            except Empty:
                time.sleep(2)
                continue
            except Exception as e:
                logger.exception(f"❌ - Erro ao processar TP para {mensagem}: {e}")
    except KeyboardInterrupt:
        logger.info("🛑 - TradeExecutorSinal interrompido pelo usuário.")

if __name__ == "__main__":
    """
    Ponto de entrada do script.

    Quando o arquivo é executado diretamente, esta instrução garante que a função `consumir_monitoramentos`
    seja chamada para iniciar o processo de consumo da fila de monitoramentos.

    Utiliza a proteção `__name__ == "__main__"` para evitar execução não intencional
    ao importar o módulo em outros scripts.
    """
    consumir_monitoramentos()
