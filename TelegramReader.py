import os
import logging
import utils
import psycopg2

from datetime import datetime
from dotenv import load_dotenv
from log.logger_config import configurar_logging
from telethon import TelegramClient, events

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
configurar_logging()
load_dotenv()

api_id = os.getenv("api_id")
api_hash = os.getenv("api_hash")
session_name = os.getenv("session_name")
group_id = int(os.getenv("group_id"))

db_params = {
    "host": os.getenv("db_host"),
    "port": os.getenv("db_port"),
    "dbname": os.getenv("db_name"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password")
}

from database.db import (
    buscar_info_apos_sinal_de_monitoramento,
    ativar_break_even,
    inserir_sinal_com_multiplos_tps
)

from utils import (
    extrair_sinal_trade,
    extrair_monitoramento_json
)

conn = psycopg2.connect(**db_params)
cur = conn.cursor()

client = TelegramClient(session_name, api_id, api_hash)

async def main():
    grupo_entidade = await utils.obter_entidade(client, group_id)
    grupo_nome = getattr(grupo_entidade, 'title', f"grupo_{group_id}")
    #nome_grupo_limpo = utils.limpar_nome(grupo_nome)
    grupo_id = grupo_entidade.id
    logger.info(f"✅ Telegram Reader inciado a escuta de mensagens em grupo: {grupo_nome} e id: {grupo_id}")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        mensagem = event.text
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"[{timestamp}] Mensagem recebida:")
        logger.info(mensagem)

        sinal = extrair_sinal_trade(mensagem)
        if sinal:
            inserir_sinal_com_multiplos_tps(sinal)
            logger.info(f"✅ Sinal inserido para {sinal['pair']}")
            return

        monitoramento = extrair_monitoramento_json(mensagem)
        if monitoramento and monitoramento["tp"] == "TP2":
            info = buscar_info_apos_sinal_de_monitoramento(monitoramento["pair"])
            if info:
                ativar_break_even(info["id"])
                logger.info(f"✅ Break-even ativado para {monitoramento['pair']}")
            else:
                logger.warning(f"⚠️ Nenhuma ordem encontrada para {monitoramento['pair']} ao tentar ativar BE.")
            return

        logger.warning("❌ Não foi possível extrair sinal ou monitoramento da mensagem.")

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n🛑 Execução do TelegramReader interrompida pelo usuário.")