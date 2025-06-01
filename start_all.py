import argparse
import atexit
import logging
import os
import sys
import subprocess
import signal

from database import db
from log.logger_config import configurar_logging
from utils import carregar_config

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
atexit.register(db.fechar_pool)

configurar_logging()
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
os.makedirs("fila/sinais", exist_ok=True)
os.makedirs("fila/monitoramentos", exist_ok=True)


def salvar_env_com_base_no_config(is_testnet):
    """
        Gera o arquivo `.env` com base nas configurações do `config.properties`.

        Etapas principais:
        1. Carrega as configurações via `carregar_config()`.
        2. Define as variáveis de ambiente com base em `is_testnet`.
        3. Gera as variáveis para broker, banco de dados, Telegram e trade.
        4. Escreve todas as variáveis no arquivo `.env`.

        Parâmetros:
        - is_testnet (bool): Define se o ambiente é testnet (True) ou mainnet (False).
        """
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
    """
    Inicia o processo separado para escutar mensagens do Telegram.

    - Executa o arquivo `TelegramReader.py` como subprocesso.
    - Registra início no log com ícone visual.

    Retorna:
    - subprocess.Popen: Instância do processo iniciado.
    """
    logger.info("🚦 - Iniciando Telegram Reader...")
    return subprocess.Popen([sys.executable, "TelegramReader.py"])

def iniciar_executor_sinal():
    """
    Inicia o executor de sinais (entrada de ordens) como subprocesso.

    - Executa `TradeExecutorSinal.py`.
    - Usado para lidar com sinais extraídos do Telegram.

    Retorna:
    - subprocess.Popen: Processo do executor de sinal.
    """
    logger.info("📈 - Iniciando TradeExecutorSinal...")
    return subprocess.Popen([sys.executable, "TradeExecutorSinal.py"])

def iniciar_executor_tp():
    """
    Inicia o executor de monitoramento de Take Profits (TP) como subprocesso.

    - Executa `TradeExecutorTP.py`.
    - Responsável por reagir a mensagens de monitoramento.

    Retorna:
    - subprocess.Popen: Processo do executor de TPs.
    """
    logger.info("📈 - Iniciando TradeExecutorTP...")
    return subprocess.Popen([sys.executable, "TradeExecutorTP.py"])


processos = []

def iniciar_componentes():
    """
    Inicia todos os componentes principais do sistema em subprocessos.

    Etapas principais:
    1. Inicia o Telegram Reader.
    2. Inicia o TradeExecutorSinal.
    3. Inicia o TradeExecutorTP.
    4. Aguarda todos os subprocessos com `.wait()`.
    5. Se houver interrupção por teclado (CTRL+C), aciona `finalizar_programa()`.

    Observações:
    - Os processos iniciados são salvos na variável global `processos`.
    """
    global processos
    processos = [
        iniciar_telegram_reader(),
        iniciar_executor_sinal(),
        iniciar_executor_tp()
    ]

    try:
        for p in processos:
            p.wait()
    except KeyboardInterrupt:
        logger.warning("🛑 - Execução interrompida pelo usuário.")
        finalizar_programa()


def finalizar_programa(*_):
    """
    Encerra graciosamente a aplicação e todos os subprocessos.

    Etapas principais:
    1. Registra encerramento no log.
    2. Para cada subprocesso ativo:
       - Verifica se ainda está rodando com `poll()`.
       - Termina o processo com `terminate()`.
    3. Fecha pool de conexões com o banco via `db.fechar_pool()`.
    4. Encerra a aplicação com `sys.exit(0)`.

    Este método é registrado como handler para os sinais `SIGINT` e `SIGTERM`.
    """
    logger.info("🛑 - Encerrando aplicação por sinal do sistema...")
    for p in processos:
        if p.poll() is None:  # ainda está rodando
            logger.warning(f"🔪 - Matando processo PID {p.pid}")
            p.terminate()
    db.fechar_pool()
    sys.exit(0)

signal.signal(signal.SIGINT, finalizar_programa)
signal.signal(signal.SIGTERM, finalizar_programa)

if __name__ == "__main__":
    """
    Ponto de entrada principal da aplicação.

    Etapas executadas:
    1. Configura o logger e diretórios necessários.
    2. Define e processa argumentos da CLI:
       - `--testnet`: Executa ambiente de testes.
       - `--mainnet`: Executa ambiente de produção.
    3. Gera o arquivo `.env` com as configurações carregadas.
    4. Inicia os subprocessos do sistema (Reader, ExecutorSinal, ExecutorTP).

    Uso recomendado:
    - `python start_all.py --testnet`
    - `python start_all.py --mainnet`
    """
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