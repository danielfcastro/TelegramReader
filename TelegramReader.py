
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel
from telethon.errors import ChannelInvalidError
from datetime import datetime
import sqlite3
import os
import re
import json
import logging

# Configurar pastas de logs e jsons
if not os.path.exists('logs/jsons'):
    os.makedirs('logs/jsons')

logging.basicConfig(
    filename='logs/telegram_reader.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Função para carregar configurações
def carregar_config(path):
    config = {}
    if not os.path.exists(path):
        print(f"Arquivo de configuração {path} não encontrado.")
        exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#'):
                chave, valor = linha.split('=', 1)
                config[chave.strip()] = valor.strip()
    return config

temp_config = carregar_config('config.properties')
api_id = int(temp_config['api_id'])
api_hash = temp_config['api_hash']
grupo_padrao = int(temp_config['grupo_id'])
db_path = temp_config.get('sqlite_db_path', 'database/sinais_novo.db')

session_name = 'minha_sessao'
client = TelegramClient(session_name, api_id, api_hash)

def criar_conexao():
    if not os.path.exists('database'):
        os.makedirs('database')
    return sqlite3.connect(db_path)

def limpar_simbolos(texto):
    return texto.replace('💸', '').replace('🕒', '').replace('✅', '')

def salvar_json(dados, prefixo="mensagem"):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"logs/jsons/{prefixo}_{timestamp}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def limpar_par(texto):
    match = re.search(r'\[(.*?)\/USDT\]', texto)
    if match:
        return match.group(1) + '/USDT'
    match = re.search(r'(\w+\/USDT)', texto)
    if match:
        return match.group(1)
    return texto

def extrair_sinal(texto):
    try:
        linhas = texto.split('\n')
        par = tipo_ordem = margem = alavancagem = ''
        entrada_inferior = entrada_superior = 0.0
        tp1 = tp2 = tp3 = tp4 = 0.0
        stoploss = 0.0

        for linha in linhas:
            linha = linha.strip()
            if '/' in linha and ('LONG' in linha or 'SHORT' in linha):
                par = limpar_par(linha)
                tipo_ordem = 'LONG' if 'LONG' in linha else 'SHORT'
            elif linha.startswith('Margin:'):
                partes = linha.split(',')
                margem = partes[0].split(':')[-1].strip()
                alavancagem = partes[1].strip() if len(partes) > 1 else ''
            elif linha.startswith('ENTRY:'):
                match = re.search(r'<(.*?)>', linha)
                if match:
                    entrada_inferior, entrada_superior = map(float, match.group(1).split('-'))
            elif 'TARGETS' in linha:
                continue
            elif re.match(r'\d+\. \[.*?\]', linha):
                numeros = re.findall(r'\[(.*?)\]', linha)
                if len(numeros) >= 1: tp1 = float(numeros[0])
                if len(numeros) >= 2: tp2 = float(numeros[1])
                if len(numeros) >= 3: tp3 = float(numeros[2])
                if len(numeros) >= 4: tp4 = float(numeros[3])
            elif 'STOPLOSS' in linha:
                stoploss = float(re.findall(r'\[(.*?)\]', linha)[0])

        if not par or not tipo_ordem:
            return None

        return {
            'data_hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'par': par,
            'tipo_ordem': tipo_ordem,
            'margem': margem,
            'alavancagem': alavancagem,
            'entrada_inferior': entrada_inferior,
            'entrada_superior': entrada_superior,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'tp4': tp4,
            'stoploss': stoploss,
            'texto_original': texto,
            'flag_executado': 0
        }
    except Exception as e:
        logging.error(f"Erro ao extrair sinal: {e}")
        return None

def extrair_monitoramento(texto):
    try:
        linhas = texto.split('\n')
        pair = price = profit = spent = instruction = tp_done = None

        for linha in linhas:
            linha = linha.strip()
            if '/' in linha and 'USDT' in linha:
                pair = linha
            elif linha.startswith('Price'):
                price = float(linha.split(' ')[-1])
            elif 'Profit' in linha:
                match = re.search(r'>(\s*)(\d+)', linha)
                if match:
                    profit = int(match.group(2))
            elif 'TARGET' in linha and 'DONE' in linha:
                match = re.search(r'TARGET #(\d+) DONE', linha)
                if match:
                    tp_done = f"tp{match.group(1)}"
            elif linha.startswith('Spent'):
                spent = linha.split(':', 1)[-1].strip()
            elif linha.startswith('*') or linha.startswith('__*'):
                instruction = linha.replace('__*', '').replace('*', '').strip()

        return {
            'pair': pair,
            'price': price,
            'profit': profit,
            'spent': spent,
            'instruction': instruction,
            'target_done': tp_done
        }
    except Exception as e:
        logging.error(f"Erro ao extrair monitoramento: {e}")
        return None

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
            grupo_entidade = await client.get_entity(int(id_input))
        else:
            print("Escolha inválida.")
            return

    print("\nMonitorando mensagens no grupo...")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        if event.text:
            texto_limpo = limpar_simbolos(event.text)
            logging.info(f"Mensagem recebida: {texto_limpo}")
            if 'ENTRY:' not in texto_limpo:
                dados_monitor = extrair_monitoramento(texto_limpo)
                if dados_monitor:
                    salvar_json(dados_monitor, prefixo="monitoramento")
                    print("\n📋 Monitoramento capturado:")
                    print(json.dumps(dados_monitor, indent=2))
            else:
                sinal = extrair_sinal(texto_limpo)
                if sinal:
                    inserir_sinal(sinal)
                    salvar_json({
                        'tipo': 'sinal',
                        **sinal
                    }, prefixo="sinal")
                else:
                    logging.warning("Não foi possível extrair sinal da mensagem.")

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n🛑 Encerrando monitoramento de mensagens...")
        client.disconnect()
        print("✅ Cliente desconectado com sucesso. Até mais!")
