
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from extrator_sinal import extrair_sinal_trade, extrair_monitoramento_json
import psycopg2

load_dotenv()

api_id = os.getenv("api_id")
api_hash = os.getenv("api_hash")
session_name = os.getenv("session_name")
grupo_entidade = int(os.getenv("group_id"))

db_params = {
    "host": os.getenv("db_host"),
    "port": os.getenv("db_port"),
    "dbname": os.getenv("db_name"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password")
}

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

def inserir_sinal(sinal):
    sql = '''
    INSERT INTO sinais (
        data_hora, par, tipo_ordem, margem, alavancagem,
        entrada_inferior, entrada_superior,
        tp1, tp2, tp3, tp4, stoploss, flag_executado
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s,
        %s, %s, %s, %s, %s, 0
    );
    '''
    valores = (
        datetime.now(), sinal["pair"], sinal["type"], sinal.get("margin", ""), sinal.get("leverage", ""),
        sinal["entry_low"], sinal["entry_high"],
        sinal.get("tp1"), sinal.get("tp2"), sinal.get("tp3"), sinal.get("tp4"),
        sinal["stoploss"]
    )
    print("SQL SINAL:", cur.mogrify(sql, valores).decode())
    cur.execute(sql, valores)
    conn.commit()

def inserir_monitoramento(mon):
    if mon["tp"] != "TP2" or not any("break-even" in i.lower() or "breakeven" in i.lower() for i in mon["instructions"]):
        return
    sql = "INSERT INTO break_even (data_hora, par, flag_executado) VALUES (%s, %s, 0);"
    valores = (datetime.now(), mon["pair"])
    print("SQL MONITORAMENTO:", cur.mogrify(sql, valores).decode())
    cur.execute(sql, valores)
    conn.commit()

async def main():
    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        mensagem = event.text
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] Mensagem recebida:", mensagem)
        logging.info(f"Mensagem recebida: {mensagem}")

        sinal = extrair_sinal_trade(mensagem)
        if sinal:
            inserir_sinal(sinal)
            logging.info(f"✅ Sinal inserido para {sinal['pair']}")
            return

        monitoramento = extrair_monitoramento_json(mensagem)
        if monitoramento:
            inserir_monitoramento(monitoramento)
            logging.info(f"📈 Monitoramento processado: {monitoramento['pair']}")
            return

        logging.warning("❌ Não foi possível extrair sinal ou monitoramento da mensagem.")

    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
