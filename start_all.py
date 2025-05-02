import os
import threading
from utils import carregar_config

def salvar_env_com_base_no_config(broker, is_testnet):
    config = carregar_config()

    is_testnet_str = "true" if is_testnet else "false"
    env_lines = [
        f"#broker configuration",
        f"BROKER={broker}",
        f"IS_TESTNET={is_testnet_str}",
        f"",
    ]
    if broker == "bybit":
        if is_testnet:
            env_lines.append(f"broker_api_key={config['bybit_api_key_testnet']}")
            env_lines.append(f"broker_api_secret={config['bybit_api_secret_testnet']}")
            env_lines.append(f"broker_api_url={config['bybit_api_url_testnet']}")
        else:
            env_lines.append(f"broker_api_key={config['bybit_api_key']}")
            env_lines.append(f"broker_api_secret={config['bybit_api_secret']}")
            env_lines.append(f"broker_api_url={config['bybit_api_url']}")

    env_lines.append(f"")
    env_lines.append(f"#db configuration")
    env_lines.append(f"db_type={config['db_type']}")
    env_lines.append(f"db_host={config['db_host']}")
    env_lines.append(f"db_port={config['db_port']}")
    env_lines.append(f"db_name={config['db_name']}")
    env_lines.append(f"db_user={config['db_user']}")
    env_lines.append(f"db_password={config['db_password']}")
    env_lines.append(f"")
    env_lines.append(f"#telegram configuration")
    env_lines.append(f"api_id={config['api_id']}")
    env_lines.append(f"api_hash={config['api_hash']}")
    env_lines.append(f"group_id={config['group_id']}")
    env_lines.append(f"session_name={config['session_name']}")

    with open(".env", "w") as f:
        f.write("\n".join(env_lines) + "\n")

    print("\n📄 Variáveis de ambiente definidas:")
    for linha in env_lines:
        print("  ", linha)

def iniciar_telegram_reader():
    os.system("python TelegramReader.py")

def iniciar_trade_executor():
    os.system("python TradeExecutor.py")

if __name__ == "__main__":
    print("🚀 Iniciando Telegram Signal Bot")

    print("Escolha o broker:")
    print("1 - Bybit")
    print("2 - BingX")
    broker = input("Digite 1 ou 2: ").strip()
    broker = "bybit" if broker == "1" else "bingx"

    print("Deseja usar a testnet?")
    print("1 - Sim")
    print("2 - Não (Mainnet)")
    testnet = input("Digite 1 ou 2: ").strip() == "1"

    salvar_env_com_base_no_config(broker, testnet)

    print("\n🚦 Iniciando componentes...")

    t1 = threading.Thread(target=iniciar_telegram_reader)
    t2 = threading.Thread(target=iniciar_trade_executor)

    t1.start()
    t2.start()

    try:
        t1.join()
        t2.join()
    except KeyboardInterrupt:
        print("\n🛑 Execução do bot interrompida pelo usuário.")