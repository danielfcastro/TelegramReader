from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, PeerChat
from telethon.errors import ChannelInvalidError, ChatIdInvalidError
from datetime import datetime
import os
import re

# Substitua com o seu api_id e api_hash
api_id = 1685560
api_hash = '63a1747ae3bf13a16df7d6f041fb3b68'

session_name = 'minha_sessao'
pasta_logs = 'logs'

client = TelegramClient(session_name, api_id, api_hash)

def limpar_nome(nome):
    """Remove caracteres inválidos para nome de arquivo"""
    nome = nome.replace(' ', '_')
    nome = re.sub(r'[^A-Za-z0-9_\-]', '', nome)
    return nome

def criar_pasta(path):
    """Cria a pasta se não existir"""
    if not os.path.exists(path):
        os.makedirs(path)

async def obter_entidade(client, id_input):
    """Tenta obter o grupo correto, seja canal ou chat"""
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

    escolha = input("Você quer usar [1] Nome do grupo ou [2] ID do grupo? Digite 1 ou 2: ")

    if escolha == '1':
        grupo_input = input("Digite o NOME do grupo exatamente como aparece: ").strip()
        grupo_entidade = await client.get_entity(grupo_input)
    elif escolha == '2':
        id_input = input("Digite o ID do grupo (ex: -1001234567890 ou -1682398986): ").strip()
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
