from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, PeerChat
from telethon.errors import ChannelInvalidError, ChatIdInvalidError
from datetime import datetime
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

# Carrega as configurações
temp_config = carregar_config('config.properties')

api_id = int(temp_config['api_id'])
api_hash = temp_config['api_hash']
grupo_padrao = int(temp_config['grupo_id'])

session_name = 'minha_sessao'
pasta_logs = 'logs'

client = TelegramClient(session_name, api_id, api_hash)

def limpar_nome(nome):
    nome = nome.replace(' ', '_')
    nome = re.sub(r'[^A-Za-z0-9_\-]', '', nome)
    return nome

def criar_pasta(path):
    if not os.path.exists(path):
        os.makedirs(path)

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

    grupo_id = grupo_entidade.id
    grupo_nome = getattr(grupo_entidade, 'title', f"grupo_{grupo_id}")
    nome_grupo_limpo = limpar_nome(grupo_nome)
    criar_pasta(pasta_logs)

    print(f"\nMonitorando e gravando mensagens no grupo: {grupo_nome}")
    print(f"Logs serão salvos na pasta '{pasta_logs}/'\n")

    @client.on(events.NewMessage(chats=grupo_entidade))
    async def handler(event):
        sender = await event.get_sender()
        nome = sender.first_name if sender else "Desconhecido"
        mensagem = event.text
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        data_hoje = datetime.now().strftime('%Y-%m-%d')
        nome_arquivo = os.path.join(pasta_logs, f"log_{nome_grupo_limpo}_{data_hoje}.txt")

        linha = f"[{timestamp}] [{nome}] > {mensagem}\n"

        print(linha.strip())

        with open(nome_arquivo, 'a', encoding='utf-8') as f:
            f.write(linha)

    await client.run_until_disconnected()

with client:
    client.loop.run_until_complete(main())
