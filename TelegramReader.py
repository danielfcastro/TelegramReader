import logging
import os

from persistqueue.sqlqueue import SQLiteQueue

import utils

from dotenv import load_dotenv
from telethon import TelegramClient, events
from log.logger_config import configurar_logging
from message.mensagem_sinal import MensagemSinal
from message.mensagem_tp import MensagemTP

TRADE = "trade"
MONITORAMENTO = "monitoramento"

# Filas (substituíveis por filas externas)
fila_sinal = SQLiteQueue(os.path.join("fila", "sinais"), auto_commit=False)
fila_tp = SQLiteQueue(os.path.join("fila", "monitoramentos"), auto_commit=False)

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
    Função principal assíncrona que inicia a escuta de mensagens no grupo Telegram definido no `.env`.

    Etapas principais:
    1. Obtém a entidade do grupo a partir do ID.
    2. Registra um handler para eventos de novas mensagens no grupo.
    3. Cada mensagem recebida é classificada como:
    - Sinal de trade (tipo "trade"): convertida em `MensagemSinal` e adicionada à fila `fila_sinal`.
    - Monitoramento (tipo "monitoramento"): convertida em `MensagemTP` e adicionada à fila `fila_tp`.
    - Outro tipo: descartado com log de aviso.
    4. As filas `fila_sinal` e `fila_tp` serão processadas por componentes consumidores posteriores.
    """
    grupo_entidade = await utils.obter_entidade(client, group_id)
    grupo_nome = getattr(grupo_entidade, 'title', f"grupo_{group_id}")
    grupo_id = grupo_entidade.id
    logger.info(f"✅ - Telegram Reader iniciado a escuta de mensagens em grupo: {grupo_nome} e id: {grupo_id}")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        """
        Handler assíncrono de mensagens novas recebidas no grupo monitorado do Telegram.

        Etapas:
        - Lê o conteúdo da mensagem recebida.
        - Usa a função `classificar_mensagem` do módulo `utils` para determinar o tipo.
        - Com base no tipo:
            - Se for `trade`: instancia `MensagemSinal`, enfileira na `fila_sinal` e registra log.
            - Se for `monitoramento`: instancia `MensagemTP`, enfileira na `fila_tp` e registra log.
            - Se não reconhecido: ignora e registra log de advertência.

        :param event: Objeto de evento do Telethon que representa a nova mensagem.
        :type event: telethon.events.NewMessage.Event
        """
        mensagem = event.text
        logger.info("📩 - Mensagem recebida. Classificando...")
        resultado = utils.classificar_mensagem(mensagem)
        tipo = resultado["tipo"]
        dados = resultado["dados"]
        logger.debug(f"📩 - tipo: {tipo} - dados: {dados} - resultado: {resultado}")

        if tipo == TRADE:
            try:
                msg = MensagemSinal(**dados)
                fila_sinal.put(msg.to_dict())
                logger.info(f"✅ - Sinal enfileirado: {msg.symbol}")
            except Exception as e:
                logger.exception(f"❌ - Erro ao processar sinal: {e}")
                return None


        elif tipo == MONITORAMENTO:
            try:
                msg = MensagemTP(**dados)
                fila_tp.put(msg.to_dict())
                logger.info(f"✅ - TP enfileirado: {msg.symbol} - {msg.tp}")
            except Exception as e:
                logger.exception(f"❌ Erro ao processar monitoramento: {e}")
                return None
        else:
            logger.warning("❌ - Mensagem não reconhecida como sinal ou TP.")
            return None

    await client.run_until_disconnected()

if __name__ == "__main__":
    """
    Bloco principal que inicia a execução do cliente Telegram com `main()`.

    - Usa `client.loop.run_until_complete(main())` para iniciar o loop assíncrono.
    - Captura interrupções com `KeyboardInterrupt` para encerrar o processo com segurança.
    """
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("🚩 - Execução do TelegramReader interrompida pelo usuário.")
