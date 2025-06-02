import logging
import os
import time

from persistqueue import SQLiteQueue

import database
from persistqueue.exceptions import Empty

from message.mensagem_sinal import MensagemSinal
from integration.BingXBroker import BingXBroker
from utils import ajustar_quantidade
from log.logger_config import configurar_logging

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
fila = SQLiteQueue(os.path.join("fila", "sinais"), auto_commit=False)

proporcoes = [0.1, 0.2, 0.5, 0.2]
REQUIRED_MARGIN_TYPE = "CROSSED"
configurar_logging()
def consumir_sinais():
    """
    Função principal responsável por consumir e processar mensagens da fila de sinais (entrada de ordens).

    Etapas principais:
    1. Inicializa o broker BingX.
    2. Entra em loop infinito para consumir a fila persistente de sinais.
    3. Para cada item na fila:
       - Verifica se a mensagem é válida (tipo dict).
       - Constrói um objeto `MensagemSinal`.
       - Obtém o preço de mercado e o tipo de margem atual.
       - Caso necessário, altera a margem para `CROSSED`.
       - Recupera o saldo disponível da conta.
       - Calcula o valor da operação com base no percentual configurado (TRADE_PERCENTAGE).
       - Calcula a quantidade de ativos a negociar com base no saldo e no preço.
       - Envia a ordem para o broker com TP e SL embutidos.
       - Se sucesso:
           - Insere ordem no banco com order_id, preço médio e quantidade.
           - Para cada Take Profit (TP1 a TP4):
               - Calcula quantidade proporcional e configura o TP no broker.
               - Se sucesso, armazena os TPs configurados para persistência.
           - Insere os TPs no banco.
           - Marca a tarefa como concluída na fila.
       - Se falhar:
           - Registra erro no log.

    4. Em caso de fila vazia (`Empty`), aguarda 2 segundos antes de tentar novamente.
    5. Em caso de exceções genéricas, registra no log sem parar o consumo.
    6. Permite interrupção limpa via `KeyboardInterrupt`.

    :return: None
    """
    logger.info(f"✅ - TradeExecutorSinal iniciado.")
    logger.debug(f"📦 - Tamanho inicial da fila Sinal: {fila.qsize()}")
    broker = BingXBroker()
    _retorno = None
    try:
        while True:
            try:
                mensagem = fila.get(timeout=2)

                if not isinstance(mensagem, dict):
                    logger.warning(f"⚠️ - Mensagem inválida recebida na fila de sinais.")
                    continue

                msg = MensagemSinal(**mensagem)
                logger.debug(f"📦 - Mensagem: {msg}")
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
                _tipo_ordem = msg.tipo_ordem.upper()
                #Recupera o risco do trade na forma de percentagem do saldo
                trade_percentage = float(os.getenv("TRADE_PERCENTAGE", "3"))
                #Calcula o valor monetário da trade
                valor_trade = saldo * (trade_percentage / 100)
                #Calcula a quantidade de moedas para o trade
                quantidade_total = ajustar_quantidade(valor_trade / preco_mercado, step=0.0001)
                #Envia a ordem
                _retorno = broker.enviar_ordem_tp_sl(msg, quantidade_total)

                if _retorno["sucesso"]:
                    #Insere a ordem no banco com o id da ordem e o preço de envio
                    order_id = _retorno["order_id"]
                    average_price= _retorno["average_price"]
                    quantidade = _retorno["quantidade"]
                    erro = _retorno["erro"]
                    erro_msg = _retorno["msg"]
                    database.sinal.ordem_inserir(msg.to_dict(), order_id, average_price, quantidade)
                    _tipo_ordem = "SELL" if _tipo_ordem == "SHORT" else "BUY"
                    side = "SELL" if _tipo_ordem.upper() == "BUY" else "BUY"
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
                    logger.info(f"✅ - Ordem enviada e TPs configurados com sucesso: {msg.symbol}")
                    fila.task_done()
                else:
                    logger.info(f"❌ - Erro ao enviar ordem para {msg.symbol}: {_retorno['msg']}")
                    fila.task_done()

            except Empty:
                time.sleep(2)
                continue
            except Exception as e:
                logger.error(f"❌ Erro ao processar mensagem de sinal: {e}")
    except KeyboardInterrupt:
        logger.info("🛑 - TradeExecutorSinal interrompido pelo usuário.")

if __name__ == "__main__":
    """
    Ponto de entrada do script.

    Quando o arquivo é executado diretamente, esta instrução garante que a função `consumir_sinais`
    seja chamada para iniciar o processo de consumo da fila de sinais.

    Utiliza a proteção `__name__ == "__main__"` para evitar execução não intencional
    ao importar o módulo em outros scripts.
    """
    consumir_sinais()
