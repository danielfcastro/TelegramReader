import hmac
import hashlib
import time
import requests
import json
import os

def carregar_config(path='config.properties'):
    config = {}
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo de configuração {path} não encontrado.")
    with open(path, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#') and '=' in linha:
                chave, valor = linha.split('=', 1)
                config[chave.strip()] = valor.strip()
    return config

config = carregar_config()

def get_bybit_balance_v5(api_key, api_secret, account_type="UNIFIED", testnet=False):
    base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
    endpoint = "/v5/account/wallet-balance"
    recv_window = "5000"
    timestamp = str(int(time.time() * 1000))

    query_string = f"accountType={account_type}"
    sign_payload = f"{timestamp}{api_key}{recv_window}{query_string}"

    signature = hmac.new(
        bytes(api_secret, "utf-8"),
        bytes(sign_payload, "utf-8"),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": signature,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "Content-Type": "application/json"
    }

    url = f"{base_url}{endpoint}?{query_string}"
    response = requests.get(url, headers=headers)
    print("Status Code:", response.status_code)
    print("Resposta bruta:")
    print(response.text)

    try:
        return response.json()
    except Exception as e:
        print("Erro ao decodificar JSON:", e)
        return {}

if __name__ == "__main__":
    api_key = config.get("bybit_api_key")
    api_secret = config.get("bybit_api_secret")

    print("🔍 Consultando saldo via API V5 da Bybit (com headers corrigidos)...")
    resultado = get_bybit_balance_v5(api_key, api_secret, account_type="UNIFIED", testnet=False)

    print("\nResultado formatado:")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
