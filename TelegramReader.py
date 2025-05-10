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
    inserir_sinal
)

from utils import (
    classificar_mensagem
)

conn = psycopg2.connect(**db_params)
cur = conn.cursor()

client = TelegramClient(session_name, api_id, api_hash)
proporcoes = [0.1, 0.2, 0.5, 0.1, 0.1]

def inserir_sinal_com_multiplos_tps(dados):
    agora = datetime.utcnow().isoformat()

    for i, proporcao in enumerate(proporcoes, start=1):
        novo_sinal = {
            "data_hora": agora,
            "par": dados["pair"],
            "tipo_ordem": dados["type"],
            "margem": dados.get("margin", "Cross"),
            "alavancagem": dados.get("leverage", "20X"),
            "proporcao": proporcao,
            "sl": dados["stoploss"]
        }

        if i <= len(proporcoes) - 1:  # Os 4 primeiros têm TP
            tp_key = f"tp{i}"
            novo_sinal["tp"] = dados[tp_key]
            logger.info(f"📥 Inserindo sinal com TP{i}: {novo_sinal}")
        else:
            logger.info(f"📥 Inserindo ordem sem TP (lote livre): {novo_sinal}")

        id_inserido = inserir_sinal(novo_sinal)
        logger.debug(f"🆔 ID gerado para ordem {i}: {id_inserido}")


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

        if tipo == "trade":
            #com base no sinal do Telegram que vem com 4 TPs eu insiro isso na tabela public.sinais
            inserir_sinal_com_multiplos_tps(dados, proporcoes)
            logger.info(f"✅ - Sinal inserido para {dados['pair']}")
            return
        elif tipo == "monitoramento":
            if dados["tp"] in ["TP2", "TP4"]:
                info = buscar_info_apos_sinal_de_monitoramento(dados["pair"])
                if info:
                    ativar_break_even(info["id"])
                    logger.info(f"✅ - Break-even ativado para {dados['pair']}")
                else:
                    logger.warning(f"⚠️ - Nenhuma ordem encontrada para {dados['pair']} ao tentar ativar BE.")
                return
        else:
            logger.warning("❌ - Não foi possível extrair sinal ou monitoramento da mensagem.")
        logger.info("✅ - Mensagem recebida e classificada.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("🛑 - Execução do TelegramReader interrompida pelo usuário.")