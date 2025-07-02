import logging
import os
import time

from persistqueue import SQLiteQueue

#import database
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
    logger.info(f"📦 - Tamanho inicial da fila TP: {fila.qsize()}")
    broker = BingXBroker()
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
                #Recupero as ordens enviadas, sl, tp e de mercado
                ordens_ativas = broker.lista_todas_as_ordens(symbol=symbol)
                logger.debug(f"📦 - Ordens Ativas: {ordens_ativas}")
                quantidade = 0.0
                entry_price = 0.0
                current_order_side = None
                order_id = None
                if ordens_ativas and ordens_ativas.get("data") and ordens_ativas["code"] == 0:
                    for ordem in ordens_ativas["data"]["orders"]:
                        if ordem["type"] == "TAKE_PROFIT_MARKET" and ordem["status"] == "NEW":
                            quantidade += float(ordem["origQty"])
                        elif ordem["type"] == "MARKET":
                            order_id = ordem["orderId"]
                            entry_price = ordem["avgPrice"]
                            current_order_side = ordem["side"]

                if not order_id:
                    logger.warning(f"⚠️ - Nenhuma ordem MARKET encontrada para {symbol}")
                    fila.task_done()
                    continue

                #Atribui order_id a mensagem
                msg.order_id = order_id
                logger.debug(f"📦 - Mensagem: {msg}")
                #Ajuste do stop price igual ao preço de entrada
                stop_price = entry_price

                # Lógica para ajustar Stop Loss após TP
                if numero_tp == 2 or numero_tp == 3:
                    sucesso = broker.ajustar_stop_loss(
                        symbol=symbol,
                        position_side="BOTH",
                        quantity=quantidade,
                        stop_price=stop_price,
                        order_id=order_id,
                        current_order_side=current_order_side
                    )
                    #Se não deu certo a chamada desfaz o update passando o status anterior
                    if not sucesso:
                        logger.error(f"❌ - TP{numero_tp} não processado com sucesso para {symbol}.")
                    else:
                        logger.info(f"✅ - TP{numero_tp} processado com sucesso para {symbol}.")
                elif numero_tp == 4:
                    broker.fecha_ordem_mercado(symbol=symbol)
                    time.sleep(1.1)
                    broker.cancela_ordem_tp(symbol=symbol)
                    time.sleep(1.1)
                    broker.cancela_ordem_sl(symbol=symbol)
                fila.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.exception(f"❌ - Erro ao processar TP para {e}")
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
