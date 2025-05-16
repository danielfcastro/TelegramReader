import logging
import os
import psycopg2
import requests
from dotenv import load_dotenv
from telethon import TelegramClient, events
from datetime import datetime, timezone

import database.db
import utils
from log.logger_config import configurar_logging

TRADE = "trade"
MONITORAMENTO = "monitoramento"

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
configurar_logging()
load_dotenv()

api_id = os.getenv("api_id")
api_hash = os.getenv("api_hash")
session_name = os.getenv("session_name")
group_id = int(os.getenv("group_id"))

ENDPOINT_SINAL = "http://127.0.0.1:8000/sinal"
ENDPOINT_MONITORAMENTO = "http://127.0.0.1:8000/monitoramento"

db_params = {
    "host": os.getenv("db_host"),
    "port": os.getenv("db_port"),
    "dbname": os.getenv("db_name"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password")
}

from utils import (
    classificar_mensagem
)

conn = psycopg2.connect(**db_params)
cur = conn.cursor()

client = TelegramClient(session_name, api_id, api_hash)
proporcoes = [0.1, 0.2, 0.5, 0.2]

def ordem_inserir_com_multiplos_tps(dados):
    agora = datetime.now(timezone.utc)

    tipo_ordem = dados["type"]
    if tipo_ordem.upper() == "LONG":
        tipo_ordem = "BUY"
    elif tipo_ordem.upper() == "SHORT":
        tipo_ordem = "SELL"

    novo_sinal = {
        "data_hora": agora,
        "par": dados["pair"],
        "tipo_ordem": tipo_ordem,
        "margem": dados.get("margin", "Cross"),
        "alavancagem": dados.get("leverage", "20X"),
        "sl": dados["stoploss"],
        "quantidade": dados.get("quantidade", 0)
    }

    logger.info(f"📅 - Inserindo novo sinal: {novo_sinal}")

    take_profits = []
    for i, proporcao in enumerate(proporcoes, start=1):
        tp_key = f"tp{i}"
        if tp_key in dados:
            take_profits.append({
                "numero": i,
                "valor": dados[tp_key],
                "proporcao": proporcao
            })

    id_sinal = database.db.ordem_inserir(novo_sinal, take_profits)
    logger.debug(f"🆔 - ID gerado para o sinal: {id_sinal}")

async def main():
    grupo_entidade = await utils.obter_entidade(client, group_id)
    grupo_nome = getattr(grupo_entidade, 'title', f"grupo_{group_id}")
    grupo_id = grupo_entidade.id
    logger.info(f"✅ - Telegram Reader iniciado a escuta de mensagens em grupo: {grupo_nome} e id: {grupo_id}")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        mensagem = event.text
        logger.info("🚦 - Mensagem recebida - ainda não classificada entre sinal ou monitoramento.")
        resultado = classificar_mensagem(mensagem)
        tipo = resultado["tipo"]
        dados = resultado["dados"]

        if tipo == TRADE:
            ordem_inserir_com_multiplos_tps(dados)
            try:
                payload = {
                    "pair": dados["pair"],
                    "type": dados["type"]
                }
                requests.post(ENDPOINT_SINAL, json=payload, timeout=2)
                logger.info(f"🚀 - POST /sinal enviado para {dados['pair']}")
            except Exception as e:
                logger.warning(f"❌ - Falha ao chamar /sinal: {e}")
            logger.info(f"✅ - Sinal inserido para {dados['pair']}")

        elif tipo == MONITORAMENTO:
            tp_numero = int(dados["tp"].replace("TP", ""))
            try:
                database.db.ordem_marcar_concluida(dados["pair"], tp_numero)
                logger.info(f"✅ - Ordem marcada como concluída para {dados['pair']}")
            except Exception as e:
                logger.warning(f"❌ - Erro ao marcar ordem concluída: {e}")

            ordem = database.db.ordem_info(dados["pair"], exigir_break_even_inativo=True)

            if ordem:
                if dados["tp"] == "TP1":
                    novo_sl = None
                else:
                    novo_sl = ordem["entry_price"]

                database.db.sinal_stop_loss_ajuste(ordem["id"], novo_sl)
                logger.info(f"✅ - SL sugerido para ordem {ordem['id']} = {novo_sl}")
            else:
                logger.warning(f"⚠️ - Nenhuma ordem ativa encontrada para ajuste de SL em {dados['pair']}")

            try:
                payload = {
                    "pair": dados["pair"],
                    "tp": dados["tp"],
                    "target_monitorado": dados["tp"].replace("TP", "")
                }
                logger.debug(f"🚀 - dados: {dados} - payload {payload}")
                requests.post(ENDPOINT_MONITORAMENTO, json=payload, timeout=2)
                logger.info(f"🚀 - POST /monitoramento enviado para {dados['pair']} - TP: {dados['tp']}")
            except Exception as e:
                logger.warning(f"❌ - Falha ao chamar /monitoramento: {e}")
        else:
            logger.warning("❌ - Não foi possível extrair sinal ou monitoramento da mensagem.")

        logger.info("✅ - Mensagem recebida e classificada.")

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("🚩 - Execução do TelegramReader interrompida pelo usuário.")
