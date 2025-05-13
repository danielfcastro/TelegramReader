import logging
import os
from datetime import datetime

import psycopg2
from dotenv import load_dotenv
from telethon import TelegramClient, events

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

db_params = {
    "host": os.getenv("db_host"),
    "port": os.getenv("db_port"),
    "dbname": os.getenv("db_name"),
    "user": os.getenv("db_user"),
    "password": os.getenv("db_password")
}

from database.db import (
    ordem_info,
    break_even_ativado,
    ordem_inserir
)

from utils import (
    classificar_mensagem
)

conn = psycopg2.connect(**db_params)
cur = conn.cursor()

client = TelegramClient(session_name, api_id, api_hash)
proporcoes = [0.1, 0.2, 0.5, 0.1, 0.1]

def ordem_inserir_com_multiplos_tps(dados):
    """
    Insere múltiplos registros de sinal na tabela `sinais` com diferentes proporções e Take Profits (TPs).

    Os primeiros `len(proporcoes) - 1` sinais terão valores de TP correspondentes (ex: tp1, tp2...).
    O último sinal será um lote livre (sem TP), usado para trailing stop ou gerenciamento posterior.

    Args:
        dados (dict): Dicionário com os dados do sinal extraídos do Telegram. Espera chaves como:
            - pair (str): Par de trading, ex: "BTC/USDT"
            - type (str): Tipo de ordem ("BUY" ou "SELL")
            - stoploss (float): Valor de stop loss
            - tp1..tp4 (float): Take profits (opcionalmente até tp4)
            - margin (str): Tipo de margem, ex: "Cross"
            - leverage (str): Alavancagem, ex: "20X"
    """

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

        id_inserido = ordem_inserir(novo_sinal)
        logger.debug(f"🆔 ID gerado para ordem {i}: {id_inserido}")


async def main():
    """
    Inicia o listener do Telegram para capturar mensagens de sinais de trade ou monitoramento.

    O bot escuta o grupo especificado, classifica as mensagens recebidas e:
        - Insere sinais múltiplos com TPs no banco de dados (`public.sinais`) quando detectar sinal de trade.
        - Ativa break-even automaticamente se uma mensagem de monitoramento atingir TP2 ou TP4.

    Raises:
        Exception: Em caso de falha de conexão ou erro inesperado no processamento da mensagem.
    """
    grupo_entidade = await utils.obter_entidade(client, group_id)
    grupo_nome = getattr(grupo_entidade, 'title', f"grupo_{group_id}")
    grupo_id = grupo_entidade.id
    logger.info(f"✅ - Telegram Reader iniciado a escuta de mensagens em grupo: {grupo_nome} e id: {grupo_id}")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        """
        Manipulador de eventos para novas mensagens recebidas no grupo.

        Analisa se a mensagem é um sinal de trade ou monitoramento e toma ações conforme o tipo.
        """
        mensagem = event.text
        logger.info("🚦 - Mensagem recebida - ainda não classificada entre sinal ou monitoramento.")
        resultado = classificar_mensagem(mensagem)
        tipo = resultado["tipo"]
        dados = resultado["dados"]

        if tipo == ("%s" % TRADE):
            #com base no sinal do Telegram que vem com 4 TPs eu insiro isso na tabela public.sinais
            ordem_inserir_com_multiplos_tps(dados)
            logger.info(f"✅ - Sinal inserido para {dados['pair']}")
            return
        elif tipo == ("%s" % MONITORAMENTO):
            if dados["tp"] in ["TP2", "TP4"]:
                info = ordem_info(dados["pair"])
                if info:
                    break_even_ativado(info["id"])
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