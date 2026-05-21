import json
import logging
import os


import utils
import requests

from dotenv import load_dotenv
from telethon import TelegramClient, events
from log.logger_config import configurar_logging
from message.mensagem_sinal import MensagemSinal
from message.mensagem_tp import MensagemTP

TRADE = "trade"
MONITORAMENTO = "monitoramento"


logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
configurar_logging()
load_dotenv()

api_id = os.getenv("api_id")
api_hash = os.getenv("api_hash")
session_name = os.getenv("session_name")
group_id = int(os.getenv("group_id"))

client = TelegramClient(session_name, api_id, api_hash)



def enviar_para_openclaw(signal_json):
    url = "http://192.168.100.:18789/hooks"   # ou IP do servidor se for remoto
    token = "7e58d533adcb4275422132d80b1a758a550a75304fb2e22f331bb372c44b9e37"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    try:
        r = requests.post(url, json=signal_json, headers=headers, timeout=15)
        if r.status_code == 200:
            print("✅ Sinal enviado para CryptoAnalyst")
        else:
            print(f"❌ Erro: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Falha ao enviar: {e}")

async def handler(event):
    """
    Handler assíncrono de mensagens novas recebidas no grupo monitorado do Telegram.

    Etapas:
    - Lê o conteúdo da mensagem recebida.
    - Usa a função `classificar_mensagem` do módulo `utils` para determinar o tipo.
    - Com base no tipo:
        - Se for `trade`: Envia POST para o TradeExecutorSinal (porta 8001).
        - Se for `monitoramento`: Envia POST para o TradeExecutorTP (porta 8002).
        - Opcionalmente envia para OpenClaw.
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
            logger.info(f"✅ - Sinal processado: {msg.symbol}")
            
            # Envia para OpenClaw (opcional/legado)
            enviar_para_openclaw(msg.to_dict()) 
            
            # NOVO: Envia para o Executor unificado via HTTP POST /trade
            url_trade = f"http://localhost:{os.getenv('PORT_EXECUTOR', 8001)}/trade"
            try:
                r = requests.post(url_trade, json=msg.to_dict(), timeout=15)
                if r.status_code == 200:
                    logger.info(f"🚀 - Sinal enviado com sucesso para TradeExecutor")
                else:
                    logger.error(f"❌ - Erro em TradeExecutor: {r.status_code} - {r.text}")
            except Exception as e:
                logger.error(f"❌ - Falha de conexão com TradeExecutor (/trade): {e}")

            return {"tipo": TRADE, "msg": msg.to_dict()}
        except Exception as e:
            logger.exception(f"❌ - Erro ao processar sinal: {e}")
            return {"error": str(e)}

    elif tipo == MONITORAMENTO:
        try:
            msg = MensagemTP(**dados)
            logger.info(f"✅ - MONITORAMENTO: {msg.symbol}")
            
            # Envia para OpenClaw (opcional/legado)
            enviar_para_openclaw(msg.to_dict()) 
            
            # NOVO: Envia para o Executor unificado via HTTP PUT /tp
            url_tp = f"http://localhost:{os.getenv('PORT_EXECUTOR', 8001)}/tp"
            try:
                r = requests.put(url_tp, json=msg.to_dict(), timeout=15)
                if r.status_code == 200:
                    logger.info(f"🚀 - TP enviado com sucesso para TradeExecutor")
                else:
                    logger.error(f"❌ - Erro em TradeExecutor (/tp): {r.status_code} - {r.text}")
            except Exception as e:
                logger.error(f"❌ - Falha de conexão com TradeExecutor (/tp): {e}")

            return {"tipo": MONITORAMENTO, "msg": msg.to_dict()}
        except Exception as e:
            logger.exception(f"❌ Erro ao processar monitoramento: {e}")
            return {"error": str(e)}
    else:
        logger.warning("❌ - Mensagem não reconhecida como sinal ou TP.")
        return None

async def main():
    """
    Função principal assíncrona que inicia a escuta de mensagens no grupo Telegram definido no `.env`.
    """
    grupo_entidade = await utils.obter_entidade(client, group_id)
    grupo_nome = getattr(grupo_entidade, 'title', f"grupo_{group_id}")
    grupo_id = grupo_entidade.id
    logger.info(f"✅ - Telegram Reader iniciado a escuta de mensagens em grupo: {grupo_nome} e id: {grupo_id}")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def wrapper_handler(event):
        resultado = await handler(event)
        if resultado:
            logger.debug(f"📊 - Mensagem: \n{json.dumps(resultado, indent=4)}")

    await client.run_until_disconnected()

if __name__ == "__main__":
    """
    Bloco principal que inicia a execução do cliente Telegram com `main()`.

    - Usa `client.loop.run_until_complete(main())` para iniciar o loop assíncrono.
    - Captura interrupções com `KeyboardInterrupt` para encerrar o processo com segurança.
    """
    import asyncio
    import sqlite3
    import time
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    tentativas = 5
    for i in range(tentativas):
        try:
            with client:
                client.loop.run_until_complete(main())
            break
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and i < tentativas - 1:
                logger.warning(f"⚠️ - Banco de dados travado. Tentando novamente em 2s... ({i+1}/{tentativas})")
                time.sleep(2)
            else:
                logger.exception(f"❌ - Erro fatal ao iniciar sessão: {e}")
                break
        except KeyboardInterrupt:
            logger.info("🚩 - Execução do TelegramReader interrompida pelo usuário.")
            break
        except Exception as e:
            logger.exception(f"❌ - Erro inesperado: {e}")
            break
