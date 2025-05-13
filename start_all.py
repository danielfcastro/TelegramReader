import argparse
import logging
import os
import sys
import threading
import atexit

from TradeExecutor import iniciar_executor
from database import db
from integration.BingXBroker import BingXBroker
from log.logger_config import configurar_logging
from utils import carregar_config

# Diretório de logs
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
atexit.register(db.fechar_pool)

# Configuração global de logging
configurar_logging()
broker=None

# Silenciar logs detalhados de utils, mostrando apenas WARNING ou mais graves
#logging.getLogger("utils").setLevel(logging.WARNING)
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])

def salvar_env_com_base_no_config(_broker, is_testnet):
    """
    Gera um arquivo `.env` com base nas configurações do `config.properties` para uso pelo restante da aplicação.

    Args:
        _broker (str): Nome do broker (ex: "bingx").
        is_testnet (bool): Se `True`, configura para rede de testes; caso contrário, para rede principal.
    """
    config = carregar_config()
    is_testnet_str = "true" if is_testnet else "false"
    env_lines = [
        f"#broker configuration",
        f"BROKER={_broker}",
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
        "",
        "#trade configuration",
        f"trade_percentage={config['trade_percentage']}"
    ])

    with open(".env", "w") as f:
        f.write("\n".join(env_lines) + "\n")

    logger.debug("📄 - Variáveis de ambiente definidas:")
    for linha in env_lines:
        logger.debug("  %s", linha)

def iniciar_telegram_reader():
    """
    Inicia o componente de leitura de mensagens do Telegram, executando o script `TelegramReader.py`
    em uma thread separada.
    """
    logger.info("🚦 - Iniciando Telegram Reader...")
    os.system("python TelegramReader.py")

def iniciar_trade_executor(_broker):
    """
    Inicia o componente de execução de ordens com base nos sinais salvos, em uma thread separada.

    Args:
        _broker (BrokerInterface): Instância do broker (ex: BingXBroker) para enviar ordens.
    """
    executor_loop = iniciar_executor(_broker)
    executor_loop()

def iniciar_com_broker(broker_name):
    """
    Inicializa os dois componentes principais:
      - Leitor de sinais do Telegram
      - Executor de ordens na corretora

    Ambos são iniciados em threads daemonizadas.

    Args:
        broker_name (str): Nome do broker (ex: "bingx").
    """
    if broker_name == "bingx":
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
        logger.warning("🛑 - Execução do bot interrompida pelo usuário.")
        sys.exit(0)

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
            "   \033[97mpython seu_arquivo.py --testnet\033[0m     \033[90m# Executa em ambiente de testes\033[0m\n"
            "   \033[97mpython seu_arquivo.py --mainnet\033[0m     \033[90m# Executa em ambiente de produção\033[0m"
        ),
        formatter_class=argparse.RawTextHelpFormatter

    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--testnet", action="store_true", help="Usar ambiente de testes (testnet)")
    group.add_argument("--mainnet", action="store_true", help="Usar ambiente de produção (mainnet)")

    args = parser.parse_args()

    testnet = args.testnet
    broker = "bingx"

    salvar_env_com_base_no_config(broker, testnet)

    logger.info("🚦 - Iniciando componentes...")
    iniciar_com_broker(broker)