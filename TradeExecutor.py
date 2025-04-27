import sqlite3
import os
import time
import hmac
import hashlib
import requests
from datetime import datetime

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

bybit_api_key = temp_config['bybit_api_key']
bybit_api_secret = temp_config['bybit_api_secret']
trade_percentage = float(temp_config.get('trade_percentage', 3))
db_path = temp_config.get('sqlite_db_path', 'database/sinais.db')

BYBIT_TESTNET_URL = "https://api-testnet.bybit.com"

def criar_conexao():
    """Cria a conexão com o banco de dados."""
    return sqlite3.connect(db_path)

def gerar_assinatura(api_secret, params):
    """Gera a assinatura HMAC-SHA256 para a ByBIT."""
    sorted_params = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    return hmac.new(
        api_secret.encode('utf-8'),
        sorted_params.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def consultar_saldo():
    endpoint = "/v2/private/wallet/balance"
    url = BYBIT_TESTNET_URL + endpoint
    timestamp = str(int(time.time() * 1000))
    params = {
        "api_key": bybit_api_key,
        "timestamp": timestamp
    }
    params['sign'] = gerar_assinatura(bybit_api_secret, params)

    response = requests.get(url, params=params)
    data = response.json()

    if data.get('result') and 'USDT' in data['result']:
        saldo = float(data['result']['USDT']['available_balance'])
        print(f"Saldo disponível: {saldo} USDT")
        return saldo
    else:
        print("Erro ao consultar saldo:", data)
        return 0.0

def consultar_preco_atual(par):
    endpoint = "/v2/public/tickers"
    url = BYBIT_TESTNET_URL + endpoint
    params = {
        "symbol": par.replace("/", "")
    }
    response = requests.get(url, params=params)
    data = response.json()

    if data.get('result'):
        preco = float(data['result'][0]['last_price'])
        print(f"Preço atual de {par}: {preco}")
        return preco
    else:
        print("Erro ao consultar preço:", data)
        return None

def criar_ordem_limitada(par, side, qty, price, stop_loss):
    endpoint = "/v2/private/order/create"
    url = BYBIT_TESTNET_URL + endpoint
    timestamp = str(int(time.time() * 1000))

    params = {
        "api_key": bybit_api_key,
        "symbol": par.replace("/", ""),
        "side": side.capitalize(),  # "Buy" ou "Sell"
        "order_type": "Limit",
        "qty": qty,
        "price": price,
        "time_in_force": "GoodTillCancel",
        "stop_loss": stop_loss,
        "reduce_only": False,
        "close_on_trigger": False,
        "position_idx": 0,  # Cross margin
        "timestamp": timestamp
    }

    params['sign'] = gerar_assinatura(bybit_api_secret, params)

    response = requests.post(url, data=params)
    data = response.json()

    if data.get("result"):
        print(f"✅ Ordem enviada para {par} com preço {price}")
        return True
    else:
        print("Erro ao enviar ordem:", data)
        return False

def atualizar_sinal(id_sinal):
    conn = criar_conexao()
    cursor = conn.cursor()
    cursor.execute('UPDATE sinais SET flag_executado = 1 WHERE id = ?', (id_sinal,))
    conn.commit()
    conn.close()
    print(f"⚡ Sinal {id_sinal} marcado como executado.")

def processar_sinais():
    while True:
        conn = criar_conexao()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sinais WHERE flag_executado = 0 ORDER BY id ASC')
        sinais = cursor.fetchall()
        conn.close()

        for sinal in sinais:
            id_sinal, data_hora, par, tipo_ordem, margem, alavancagem, entry_min, entry_max, stoploss, targets, flag_executado = sinal

            print(f"\n🔔 Processando sinal ID {id_sinal} - {par} ({tipo_ordem})")

            saldo = consultar_saldo()
            preco_atual = consultar_preco_atual(par)

            if saldo > 0 and preco_atual:
                if entry_min <= preco_atual <= entry_max:
                    valor_para_trade = saldo * (trade_percentage / 100)
                    qty = round(valor_para_trade / preco_atual, 3)  # Arredonda para 3 casas

                    sucesso = criar_ordem_limitada(par, tipo_ordem, qty, preco_atual, stoploss)

                    if sucesso:
                        atualizar_sinal(id_sinal)
                else:
                    print(f"⏳ Preço {preco_atual} fora do intervalo {entry_min}-{entry_max}. Aguardando...")
            else:
                print("❌ Sem saldo disponível ou preço inválido.")

        print("🕒 Aguardando 30 segundos para nova verificação...")
        time.sleep(30)

if __name__ == "__main__":
    processar_sinais()
