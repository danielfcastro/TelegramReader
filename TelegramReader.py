import os
import re
import json
import logging
import sqlite3
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, PeerChat
from telethon.errors import ChannelInvalidError, ChatIdInvalidError
from extrator_sinal import extrair_sinal_trade, extrair_monitoramento_json
from utils import carregar_config, limpar_nome, criar_pasta, obter_entidade
import TradeExecutor

config = carregar_config()

api_id = int(config['api_id'])
api_hash = config['api_hash']
grupo_padrao = int(config['grupo_id'])
db_mode = config.get("database_mode", "sqlite")
db_path = config.get("sqlite_db_path", "database/sinais.db")

session_name = 'minha_sessao'
pasta_logs = 'logs'

client = TelegramClient(session_name, api_id, api_hash)

criar_pasta(pasta_logs)
criar_pasta(os.path.dirname(db_path))

logging.basicConfig(
    filename='logs/telegram_reader.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def salvar_json_arquivo(objeto, nome_base):
    nome_arquivo = os.path.join(pasta_logs, f"{nome_base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(nome_arquivo, 'w', encoding='utf-8') as f:
        json.dump(objeto, f, ensure_ascii=False, indent=2)
    logging.info(f"📁 JSON salvo em: {nome_arquivo}")

def salvar_sinal_db(sinal):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sinais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            par TEXT,
            tipo TEXT,
            entrada_inferior REAL,
            entrada_superior REAL,
            tp1 REAL,
            tp2 REAL,
            tp3 REAL,
            tp4 REAL,
            stoploss REAL,
            executado TEXT DEFAULT 'Não'
        )
    ''')
    cursor.execute('''
        INSERT INTO sinais (data, par, tipo, entrada_inferior, entrada_superior, tp1, tp2, tp3, tp4, stoploss)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        sinal['pair'], sinal['type'], sinal['entry_low'], sinal['entry_high'],
        sinal.get('tp1'), sinal.get('tp2'), sinal.get('tp3'), sinal.get('tp4'), sinal['stoploss']
    ))
    conn.commit()
    conn.close()

async def main():
    await client.start()

    usar_padrao = input(f"Usar grupo padrão do config (ID {grupo_padrao})? [s/n]: ").strip().lower()

    if usar_padrao == 's':
        grupo_entidade = await client.get_entity(PeerChannel(grupo_padrao))
    else:
        escolha = input("Você quer usar [1] Nome do grupo ou [2] ID do grupo? Digite 1 ou 2: ")
        if escolha == '1':
            grupo_input = input("Digite o NOME do grupo exatamente como aparece: ").strip()
            grupo_entidade = await client.get_entity(grupo_input)
        elif escolha == '2':
            id_input = input("Digite o ID do grupo: ").strip()
            grupo_entidade = await obter_entidade(client, id_input)
            if grupo_entidade is None:
                print("Não foi possível localizar o grupo/canal com o ID informado.")
                return
        else:
            print("Escolha inválida.")
            return

    grupo_nome = getattr(grupo_entidade, 'title', f"grupo_{grupo_entidade.id}")
    nome_grupo_limpo = limpar_nome(grupo_nome)

    print(f"\n📡 Monitorando mensagens no grupo: {grupo_nome}")
    print(f"Logs serão salvos em: {pasta_logs}/\n")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        mensagem = event.text
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        print(f"[{timestamp}] Mensagem recebida:", mensagem)
        logging.info(f"Mensagem recebida: {mensagem}")

        sinal = extrair_sinal_trade(mensagem)
        if sinal:
            logging.info(f"✅ Sinal identificado para {sinal['pair']} ({sinal['type']})")
            salvar_sinal_db(sinal)
            salvar_json_arquivo(sinal, "sinal")
            TradeExecutor.executar_trade(sinal)
            return

        monitoramento = extrair_monitoramento_json(mensagem)
        if monitoramento:
            logging.info(f"📈 Monitoramento identificado para {monitoramento['pair']}")
            salvar_json_arquivo(monitoramento, "monitoramento")

            # ✅ Lógica de break-even ao atingir TP2
            if monitoramento.get("tp") == "TP2":
                from integration.bybit_trading import set_break_even
                try:
                    with open("sinal.json", "r", encoding="utf-8") as f:
                        sinal_anterior = json.load(f)
                        if sinal_anterior["pair"].replace("/", "") == monitoramento["pair"].replace("/", ""):
                            entry_price = (sinal_anterior["entry_low"] + sinal_anterior["entry_high"]) / 2
                            set_break_even(monitoramento["pair"].replace("/", ""), entry_price)
                            logging.info(f"🎯 Stop Loss ajustado para break-even ({entry_price}) em {monitoramento['pair']}")
                        else:
                            logging.warning("❗ O par do monitoramento não corresponde ao último sinal salvo.")
                except Exception as e:
                    logging.error(f"Erro ao aplicar break-even: {e}")

            TradeExecutor.ajustar_trade(monitoramento)
            return

        logging.warning("❌ Não foi possível extrair sinal ou monitoramento da mensagem.")

    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
