import os
import importlib
import json

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

# Leitura do broker escolhido
broker = config.get("broker", "bybit").lower()
is_testnet = config.get("is_testnet", "false").lower() == "true"

# Carga dinâmica do módulo correto
if broker == "bybit":
    import bybit_trading as trading_impl
elif broker == "bingx":
    import bingx_trading as trading_impl
else:
    raise ValueError(f"Broker '{broker}' não suportado.")

def executar_trade(sinal):
    """
    Recebe um sinal de entrada e delega ao broker.
    """
    print(f"🚀 Executando trade no broker: {broker.upper()} (Testnet={is_testnet})")
    trading_impl.abrir_ordem_com_tps(sinal)

def ajustar_trade(monitoramento):
    """
    Recebe um monitoramento (ex: Fix 10% profit) e ajusta o trade.
    """
    print(f"⚙️ Ajustando trade no broker: {broker.upper()} (Testnet={is_testnet})")
    # Aqui chamaremos trading_impl.ajustar_ordem_monitoramento(monitoramento)
    # Quando a função for criada no bybit_trading.py e bingx_trading.py
    print("🔔 Ainda não implementado: ajuste de trade.")

# Exemplo de uso direto
if __name__ == "__main__":
    #with open("exemplo_sinal.json", "r", encoding="utf-8") as f:
    #    sinal = json.load(f)
    #    executar_trade(sinal)
    print(f"🚀 A espera de sinais...")
