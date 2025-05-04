import os
import threading
import sys
import logging

from utils import carregar_config
from log.logger_config import configurar_logging
from integration.BingXBroker import BingXBroker
from TradeExecutor import iniciar_executor

# Diretório de logs
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Configuração global de logging
configurar_logging()

# Silenciar logs detalhados de utils, mostrando apenas WARNING ou mais graves
#logging.getLogger("utils").setLevel(logging.WARNING)
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

def salvar_env_com_base_no_config(broker, is_testnet):
    config = carregar_config()
    is_testnet_str = "true" if is_testnet else "false"
    env_lines = [
        f"#broker configuration",
        f"BROKER={broker}",
        f"IS_TESTNET={is_testnet_str}",
        f"",
    ]

    if broker == "bingx":
        if is_testnet:
            env_lines.append(f"broker_api_key={config['bingx_apy_key']}")
            env_lines.append(f"broker_api_secret={config['bingx_secret_key']}")
            env_lines.append(f"broker_api_url={config['bingx_api_url_testnet']}")
        else:
            env_lines.append(f"broker_api_key={config['bingx_apy_key']}")
            env_lines.append(f"broker_api_secret={config['bingx_secret_key']}")
            env_lines.append(f"broker_api_url={config['bingx_api_url']}")

    env_lines.extend([
        "",
        "#db configuration",
        f"db_type={config['db_type']}",
        f"db_host={config['db_host']}",
        f"db_port={config['db_port']}",
        f"db_name={config['db_name']}",
        f"db_user={config['db_user']}",
        f"db_password={config['db_password']}",
        "",
        "#telegram configuration",
        f"api_id={config['api_id']}",
        f"api_hash={config['api_hash']}",
        f"group_id={config['group_id']}",
        f"session_name={config['session_name']}",
    ])

    with open(".env", "w") as f:
        f.write("\n".join(env_lines) + "\n")

    logger.debug("📄 Variáveis de ambiente definidas:")
    for linha in env_lines:
        logger.debug("  %s", linha)

def iniciar_telegram_reader():
    logger.info(f"🚦 Iniciando Telegram Reader...")
    os.system("python TelegramReader.py")

def iniciar_trade_executor(broker):
    executor_loop = iniciar_executor(broker)
    executor_loop()

def iniciar_com_broker(broker_name):
    broker = BingXBroker()

    t1 = threading.Thread(target=iniciar_telegram_reader, daemon=True)
    t2 = threading.Thread(target=iniciar_trade_executor, args=(broker,), daemon=True)

    t1.start()
    t2.start()
    try:
        while t1.is_alive() and t2.is_alive():
            t1.join(timeout=1)
            t2.join(timeout=1)
    except KeyboardInterrupt:
        logger.warning("\n🛑 Execução do bot interrompida pelo usuário.")
        sys.exit(0)

if __name__ == "__main__":
    logger.info("🚦 Iniciando Telegram Signal Bot")

    broker = "bingx"

    print("Deseja usar a testnet?")
    print("1 - Sim")
    print("2 - Não (Mainnet)")
    testnet = input("Digite 1 ou 2: ").strip() == "1"

    salvar_env_com_base_no_config(broker, testnet)

    logger.info("🚦 Iniciando componentes...")
    iniciar_com_broker(broker)
