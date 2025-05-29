import logging
import os
import psycopg2
import requests
from dotenv import load_dotenv
from mypy.errorcodes import RETURN
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
ENDPOINT_FECHAMENTO = "http://127.0.0.1:8000/fechamento"

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
    """
    Insere um sinal no banco com múltiplos Take Profits e aciona o serviço de execução.

    Verifica duplicidade com base em (symbol, janela_5min). Em caso de sucesso,
    envia o ID e o symbol para o endpoint /sinal.

    Args:
        dados (dict): Dicionário com os dados do sinal extraídos da mensagem do Telegram.

    Returns:
        int | None: ID do sinal inserido ou None em caso de duplicidade ou erro.
    """

    agora = datetime.now(timezone.utc)
    janela_5min = agora.replace(second=0, microsecond=0, minute=(agora.minute // 5) * 5)

    tipo_ordem = dados["type"].upper()
    tipo_ordem = "BUY" if tipo_ordem == "LONG" else "SELL"

    novo_sinal = {
        "data_hora": agora,
        "symbol": dados["symbol"],
        "tipo_ordem": tipo_ordem,
        "margem": dados.get("margin", "Cross"),
        "alavancagem": dados.get("leverage", "20X"),
        "sl": dados["stoploss"],
        "quantidade": dados.get("quantidade", 0),
        "janela_5min": janela_5min
    }

    take_profits = []
    for i, proporcao in enumerate(proporcoes, start=1):
        tp_key = f"tp{i}"
        if tp_key in dados:
            take_profits.append({
                "numero": i,
                "valor": dados[tp_key],
                "proporcao": proporcao
            })

    try:
        id_sinal = database.db.ordem_inserir(novo_sinal, take_profits)
        logger.debug(f"🆔 - ID gerado para o sinal: {id_sinal}")
    except psycopg2.errors.UniqueViolation:
        logger.warning(f"⚠️ - Sinal duplicado detectado: {dados['symbol']} @ {janela_5min}")
        return None
    except Exception as e:
        logger.exception(f"❌ - Erro ao inserir sinal: {e}")
        return None

    # Chamada ao serviço externo
    try:
        payload = {
            "id": id_sinal,
            "symbol": dados["symbol"]
        }
        requests.post(ENDPOINT_SINAL, json=payload, timeout=10)
        logger.info(f"🚀 - POST /sinal enviado com payload: {payload}")
    except Exception as e:
        logger.warning(f"❌ - Falha ao chamar /sinal: {e}")

    return id_sinal


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
        logger.info("🚦 - Mensagem recebida - ainda não classificada entre sinal ou monitoramento.")
        resultado = classificar_mensagem(mensagem)
        tipo = resultado["tipo"]

        if tipo == "invalida":
            logger.warning(f"🚫 - Mensagem inválida ignorada: {resultado.get('erro')}")
            return None

        dados = resultado["dados"]

        if tipo == TRADE:
            logger.info("✅ - Mensagem recebida e classificada. - TRADE")
            id_sinal = ordem_inserir_com_multiplos_tps(dados)
            if id_sinal is None:
                logger.info(f"🛑 - Sinal não processado (duplicado ou erro). Ignorando.")
                return None
            return None


        elif tipo == MONITORAMENTO:
            logger.info("✅ - Mensagem recebida e classificada. - MONITORAMENTO/TP")
            tp_numero = int(dados["tp"].replace("TP", ""))
            symbol = utils.normalizar_symbol(dados["symbol"])
            try:
                database.db.take_profits_atualizar(symbol=symbol, numero_tp=tp_numero, novo_status=3)
                logger.info(f"✅ - Ordem marcada como concluída para {symbol}")
            except Exception as e:
                logger.warning(f"❌ - Erro ao marcar ordem concluída: {e}")

            if tp_numero == 4:
                logger.debug("✅ - Mensagem recebida e classificada. - MONITORAMENTO/TP - CASO ESPECIAL TP4")
                logger.debug(f"🚀 TP4 - enviar para endpoint /fechamento")
                try:
                    ordem = database.db.ordem_info(symbol=symbol, exigir_break_even_inativo=False)
                    if ordem is None:
                        logger.warning(f"❌ - Nenhuma ordem encontrada no banco para symbol: {symbol}")
                        return None

                    payload = {
                        "symbol": symbol,
                        "id_sinal": ordem["id"],
                        "order_id": ordem["order_id"]
                    }
                    logger.debug(f"🚀 Ordem Info - ordem: {ordem} - payload {payload} - Take Profit: {tp_numero}")
                    requests.post(ENDPOINT_FECHAMENTO, json=payload, timeout=10)
                    logger.debug(f"🚀 - POST /fechamento enviado")
                    return tp_numero
                except Exception as e:
                    logger.error(f"❌ - Falha ao chamar /fechamento: {e}")
                    return None

            ordem = database.db.ordem_info(symbol, exigir_break_even_inativo=True)

            ativar_break_even=False
            if ordem:
                if dados["tp"] == "TP1":
                    novo_sl = ordem["sl"]
                else:
                    novo_sl = ordem["entry_price"]
                    ativar_break_even = True

                database.db.stop_loss_ajuste(id_sinal=ordem["id"], sl=novo_sl, ativar_break_even=ativar_break_even)
                logger.info(f"✅ - SL sugerido para ordem {ordem['id']} = {novo_sl}")
                try:
                    payload = {
                        "symbol": dados["symbol"],
                        "tp": dados["tp"],
                        "id_sinal": ordem["id"],
                        "order_id": ordem["order_id"],
                        "target_monitorado": dados["tp"].replace("TP", "")
                    }
                    logger.debug(f"🚀 - dados: {dados} - payload {payload}")
                    requests.post(ENDPOINT_MONITORAMENTO, json=payload, timeout=10)
                    logger.debug(f"🚀 - POST /monitoramento enviado para {dados['symbol']} - TP: {dados['tp']}")
                except Exception as e:
                    logger.error(f"❌ - Falha ao chamar /monitoramento: {e}")
                    return None
            else:
                logger.warning(f"⚠️ - Nenhuma ordem ativa encontrada para ajuste de SL em {dados['symbol']}")
        else:
            logger.warning("❌ - Não foi possível extrair sinal ou monitoramento da mensagem.")
            return None

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("🚩 - Execução do TelegramReader interrompida pelo usuário.")
