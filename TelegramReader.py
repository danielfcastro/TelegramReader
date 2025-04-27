from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, PeerChat
from telethon.errors import ChannelInvalidError, ChatIdInvalidError
from datetime import datetime
import sqlite3
import os
import re

# Função para carregar o arquivo de configuração
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

# Carregar configurações
temp_config = carregar_config('config.properties')

api_id = int(temp_config['api_id'])
api_hash = temp_config['api_hash']
grupo_padrao = int(temp_config['grupo_id'])
db_path = temp_config.get('sqlite_db_path', 'database/sinais.db')

session_name = 'minha_sessao'
client = TelegramClient(session_name, api_id, api_hash)

def limpar_nome(nome):
    nome = nome.replace(' ', '_')
    nome = re.sub(r'[^A-Za-z0-9_\-]', '', nome)
    return nome

def criar_conexao():
    """Cria a conexão com o banco de dados."""
    if not os.path.exists('database'):
        os.makedirs('database')
    return sqlite3.connect(db_path)

async def obter_entidade(client, id_input):
    try:
        return await client.get_entity(PeerChannel(int(id_input)))
    except (ChannelInvalidError, ValueError):
        pass
    try:
        return await client.get_entity(PeerChat(int(id_input)))
    except (ChatIdInvalidError, ValueError):
        pass
    return None

def extrair_sinal(texto):
    """Extrai as informações principais do sinal da mensagem."""
    try:
        # Inicializa variáveis
        par = tipo_ordem = margem = alavancagem = ''
        entry_min = entry_max = stoploss = 0.0
        targets = ''

        linhas = texto.split('\n')

        for linha in linhas:
            linha = linha.strip()
            if '/' in linha and ('LONG' in linha or 'SHORT' in linha):
                par = linha.split()[0]
                tipo_ordem = 'LONG' if 'LONG' in linha else 'SHORT'
            elif linha.startswith('Margin:'):
                partes = linha.split(',')
                margem = partes[0].split(':')[-1].strip()
                alavancagem = partes[1].strip() if len(partes) > 1 else ''
            elif linha.startswith('ENTRY:'):
                entry = linha.split('<')[-1].split('>')[0]
                entry_min, entry_max = map(float, entry.split('-'))
            elif 'STOPLOSS' in linha:
                stoploss = float(re.findall(r"[\d\.]+", linha)[0])
            elif 'TARGET' in linha or '🎯' in linha:
                targets += linha + '\n'

        if not par or not tipo_ordem:
            return None  # Não é um sinal válido

        return {
            'data_hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'par': par,
            'tipo_ordem': tipo_ordem,
            'margem': margem,
            'alavancagem': alavancagem,
            'entry_min': entry_min,
            'entry_max': entry_max,
            'stoploss': stoploss,
            'targets': targets.strip(),
            'flag_executado': 0
        }
    except Exception as e:
        print(f"Erro ao extrair sinal: {e}")
        return None

def inserir_sinal(sinal):
    """Insere o sinal no banco."""
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sinais (data_hora, par, tipo_ordem, margem, alavancagem, entry_min, entry_max, stoploss, targets, flag_executado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        sinal['data_hora'], sinal['par'], sinal['tipo_ordem'], sinal['margem'],
        sinal['alavancagem'], sinal['entry_min'], sinal['entry_max'],
        sinal['stoploss'], sinal['targets'], sinal['flag_executado']
    ))
    conn.commit()
    conn.close()
    print(f"✅ Sinal gravado no banco para {sinal['par']} ({sinal['tipo_ordem']})")

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

    print(f"\nMonitorando mensagens no grupo...")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        if event.text:
            sinal = extrair_sinal(event.text)
            if sinal:
                inserir_sinal(sinal)

    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
