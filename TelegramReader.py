import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
import utils
import psycopg2

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

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOG_DIR, "telegram_reader.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

client = TelegramClient(session_name, api_id, api_hash)

async def main():
    grupo_entidade = await utils.obter_entidade(client, group_id)
    grupo_nome = getattr(grupo_entidade, 'title', f"grupo_{group_id}")
    nome_grupo_limpo = utils.limpar_nome(grupo_nome)
    grupo_id = grupo_entidade.id 

    print(f"\nMonitorando e gravando mensagens no grupo: {grupo_nome}")
    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        mensagem = event.text
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Mensagem recebida:")
        print(mensagem)
        logging.info(f"Mensagem recebida: {mensagem}")

        sinal = extrair_sinal_trade(mensagem)
        if sinal:
            inserir_sinal_com_multiplos_tps(sinal)
            logging.info(f"✅ Sinal inserido para {sinal['pair']}")
            return

        monitoramento = extrair_monitoramento_json(mensagem)
        if monitoramento:
            if monitoramento["tp"] != "TP2" or not any("break-even" in i.lower() or "breakeven" in i.lower() for i in monitoramento["instructions"]):
                return
            info = buscar_info_apos_sinal_de_monitoramento(monitoramento["pair"])
            if info:
                ativar_break_even(info["id"])
            logging.info(f"📈 Monitoramento processado: {monitoramento['pair']}")
            return

        logging.warning("❌ Não foi possível extrair sinal ou monitoramento da mensagem.")

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n🛑 Execução do TelegramReader interrompida pelo usuário.")