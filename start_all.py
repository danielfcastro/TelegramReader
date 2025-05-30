import argparse
import atexit
import logging
import os
import sys
import threading
import signal

from database import db
from log.logger_config import configurar_logging
from utils import carregar_config

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
atexit.register(db.fechar_pool)

configurar_logging()
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

def salvar_env_com_base_no_config(is_testnet):
    config = carregar_config()
    is_testnet_str = "true" if is_testnet else "false"
    env_lines = [
        f"#broker configuration",
        f"BROKER=BingX",
        f"IS_TESTNET={is_testnet_str}",
        f"",
        f"broker_api_key={config['bingx_api_key']}",
        f"broker_api_secret={config['bingx_secret_key']}",
        f"broker_api_url={config['bingx_api_url_testnet'] if is_testnet else config['bingx_api_url']}",
        "",
        f"#db configuration",
        f"db_type={config['db_type']}",
        f"db_host={config['db_host']}",
        f"db_port={config['db_port']}",
        f"db_name={config['db_name']}",
        f"db_user={config['db_user']}",
        f"db_password={config['db_password']}",
        "",
        f"#telegram configuration",
        f"api_id={config['api_id']}",
        f"api_hash={config['api_hash']}",
        f"group_id={config['group_id']}",
        f"session_name={config['session_name']}",
        "",
        f"#trade configuration",
        f"trade_percentage={config['trade_percentage']}"
    ]

    with open(".env", "w") as f:
        f.write("\n".join(env_lines) + "\n")

    logger.debug("📄 - Variáveis de ambiente definidas.")

def iniciar_telegram_reader():
    logger.info("🚦 - Iniciando Telegram Reader...")
    os.system("python TelegramReader.py")

def iniciar_executor_sinal():
    logger.info("📤 - Iniciando TradeExecutorSinal...")
    os.system("python TradeExecutorSinal.py")

def iniciar_executor_tp():
    logger.info("📈 - Iniciando TradeExecutorTP...")
    os.system("python TradeExecutorTP.py")

def iniciar_componentes():
    t1 = threading.Thread(target=iniciar_telegram_reader, daemon=True)
    t2 = threading.Thread(target=iniciar_executor_sinal, daemon=True)
    t3 = threading.Thread(target=iniciar_executor_tp, daemon=True)

    t1.start()
    t2.start()
    t3.start()

    try:
        while t1.is_alive() or t2.is_alive() or t3.is_alive():
            t1.join(timeout=1)
            t2.join(timeout=1)
            t3.join(timeout=1)
    except KeyboardInterrupt:
        logger.warning("🛑 - Execução interrompida pelo usuário.")
        sys.exit(0)

def finalizar_programa(*_):
    logger.info("⚠️ - Encerrando aplicação por sinal do sistema...")
    db.fechar_pool()
    sys.exit(0)

signal.signal(signal.SIGINT, finalizar_programa)
signal.signal(signal.SIGTERM, finalizar_programa)

if __name__ == "__main__":
    logger.info("🚦 - Iniciando Telegram Signal Bot")

    parser = argparse.ArgumentParser(
        description=(
            "\033[92m🟢 Inicia o bot de sinais na rede desejada.\033[0m\n\n"
            "\033[93m⚠️  REQUISITOS IMPORTANTES:\033[0m\n"
            "   - Sua conta na corretora deve estar configurada da seguinte forma:\n"
            "     \033[96m• Margin Mode:\033[0m      \033[91mCROSS\033[0m\n"
            "     \033[96m• Position Mode:\033[0m    \033[91mONE-WAY\033[0m\n\n"
            "\033[91mEssas configurações são OBRIGATÓRIAS para que o bot funcione corretamente.\033[0m"
        ),
        epilog=(
            "\033[94m💡 EXEMPLOS DE USO:\033[0m\n"
            "   \033[97mpython start_all.py --testnet\033[0m     \033[90m# Executa em ambiente de testes\033[0m\n"
            "   \033[97mpython start_all.py --mainnet\033[0m     \033[90m# Executa em ambiente de produção\033[0m"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--testnet", action="store_true", help="Usar ambiente de testes (testnet)")
    group.add_argument("--mainnet", action="store_true", help="Usar ambiente de produção (mainnet)")

    args = parser.parse_args()
    salvar_env_com_base_no_config(args.testnet)

    logger.info("🚦 - Iniciando componentes...")
    iniciar_componentes()