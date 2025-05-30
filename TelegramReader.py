import logging
import os
from dotenv import load_dotenv
from telethon import TelegramClient, events

import utils
from log.logger_config import configurar_logging
from message.mensagem_sinal import MensagemSinal
from message.mensagem_tp import MensagemTP
from queue import Queue

TRADE = "trade"
MONITORAMENTO = "monitoramento"

# Filas (substituíveis por filas externas)
fila_sinal = Queue()
fila_tp = Queue()

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
configurar_logging()
load_dotenv()

api_id = os.getenv("api_id")
api_hash = os.getenv("api_hash")
session_name = os.getenv("session_name")
group_id = int(os.getenv("group_id"))

client = TelegramClient(session_name, api_id, api_hash)

async def main():
    """
    Função principal assíncrona que:

    1. Obtém a entidade do grupo configurado no Telegram.
    2. Registra o handler de mensagens recebidas.
    3. Classifica mensagens como sinal de trade ou monitoramento.
    4. Executa a lógica correspondente de inserção ou ajuste de stop loss.
    5. Envia payloads para os endpoints /sinal e /monitoramento.

    Inicia a escuta assíncrona do cliente Telegram.
    """

    grupo_entidade = await utils.obter_entidade(client, group_id)
    grupo_nome = getattr(grupo_entidade, 'title', f"grupo_{group_id}")
    grupo_id = grupo_entidade.id
    logger.info(f"✅ - Telegram Reader iniciado a escuta de mensagens em grupo: {grupo_nome} e id: {grupo_id}")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        """
        Handler que processa novas mensagens do Telegram.

        - Se for um sinal de trade:
            - Insere no banco (se não for duplicado).
            - Dispara o processo de execução via /sinal.

        - Se for um monitoramento (TP1–TP4):
            - Marca TP como concluído.
            - Se for TP2 ou TP4, prepara ajuste de SL para break-even.
            - Envia evento para /monitoramento.

        Args:
            event (telethon.events.NewMessage.Event): Evento de nova mensagem recebida.
        """

        mensagem = event.text
        logger.info("📩 - Mensagem recebida. Classificando...")
        resultado = utils.classificar_mensagem(mensagem)
        tipo = resultado["tipo"]
        dados = resultado["dados"]

        if tipo == TRADE:
            try:
                msg = MensagemSinal(**dados)
                fila_sinal.put(msg.to_dict())
                logger.info(f"✅ Sinal enfileirado: {msg.symbol}")
            except Exception as e:
                logger.exception(f"❌ Erro ao processar sinal: {e}")
                return None


        elif tipo == MONITORAMENTO:
            try:
                msg = MensagemTP(**dados)
                fila_tp.put(msg.to_dict())
                logger.info(f"✅ - TP enfileirado: {msg.symbol} - TP{msg.tp}")
            except Exception as e:
                logger.exception(f"❌ Erro ao processar monitoramento: {e}")
                return None
        else:
            logger.warning("❌ Mensagem não reconhecida como sinal ou TP.")
            return None

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("🚩 - Execução do TelegramReader interrompida pelo usuário.")
