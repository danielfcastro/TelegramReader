import os
import re
from telethon.tl.types import PeerChannel, PeerChat
from telethon.errors import ChannelInvalidError, ChatIdInvalidError

def carregar_config(path='config.properties'):
    config = {}
    if not os.path.exists(path):
        print(f"Arquivo de configuração {path} não encontrado.")
        exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#') and '=' in linha:
                chave, valor = linha.split('=', 1)
                config[chave.strip()] = valor.strip()
    return config

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

def imprimir_configuracoes_ambiente():
    print("\n📄 Variáveis de ambiente definidas:")
    for chave in ["BROKER", "IS_TESTNET", "trade_percentage", "bybit_api_key", "bybit_api_secret", "bybit_api_url"]:
        valor = os.getenv(chave)
        print(f"   {chave}={valor}")

    is_testnet = os.getenv("IS_TESTNET", "false").strip('"').lower() == "true"
    print("\n🚦 Iniciando componentes...")
    print(f"🚀 Executando trade no broker: {os.getenv('BROKER', '').upper()} (Testnet={is_testnet})")
    print("🔐 Consultando saldo para calcular valor do trade...")