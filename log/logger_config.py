# logger_config.py
import logging
import os

log_format = "%(asctime)s - %(levelname)-8s - %(name)-20s - %(funcName)-35s - %(message)s"

class ColoredFormatter(logging.Formatter):
    """
    Formatador de logs com cores ANSI, para facilitar a leitura no terminal.

    Herda de:
        logging.Formatter

    Atributos:
        COLORS (dict): Mapeia níveis de log para códigos ANSI.
        RESET (str): Código ANSI para resetar cor.

    Métodos:
        format(record): Formata a mensagem aplicando cor conforme o nível.
    """
    COLORS = {
        'DEBUG': '\033[92m',   # verde
        'INFO': '\033[0m',     # branco (default)
        'WARNING': '\033[93m', # amarelo
        'ERROR': '\033[91m',   # vermelho
        'CRITICAL': '\033[95m' # magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        """
        Aplica cor ANSI à mensagem de log com base no nível de severidade.

        Args:
            record (LogRecord): Objeto contendo os detalhes do log.

        Returns:
            str: Mensagem formatada com cor.
        """
        color = self.COLORS.get(record.levelname, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"

def configurar_logging(log_level=logging.DEBUG, log_dir='logs', log_file='app.log'):
    """
    Configura o sistema de logging para terminal e arquivo com formatação colorida e detalhada.

    - Cria diretório de logs se não existir.
    - Envia logs para console e arquivo simultaneamente.
    - Define níveis de log por módulo (start_all, utils, db etc).
    - Aplica filtros em bibliotecas de terceiros como `telethon` e `asyncio`.

    Args:
        log_level (int): Nível mínimo de log (ex: logging.DEBUG).
        log_dir (str): Diretório onde o arquivo de log será salvo.
        log_file (str): Nome do arquivo de log.
    """
    os.makedirs(log_dir, exist_ok=True)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(log_format))

    file_handler = logging.FileHandler(os.path.join(log_dir, log_file), encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))

    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler]
    )

    # Ajuste para loggers
    logging.getLogger("start_all").setLevel(logging.INFO)
    logging.getLogger("TelegramReader").setLevel(logging.DEBUG)
    logging.getLogger("TradeExecutorSinal").setLevel(logging.DEBUG)
    logging.getLogger("TradeExecutorTP").setLevel(logging.DEBUG)
    logging.getLogger("BingXBroker").setLevel(logging.DEBUG)
    logging.getLogger("utils").setLevel(logging.INFO)
    logging.getLogger("db").setLevel(logging.DEBUG)
    logging.getLogger("sinal").setLevel(logging.DEBUG)
    logging.getLogger("stop_loss").setLevel(logging.DEBUG)
    logging.getLogger("take_profit").setLevel(logging.DEBUG)

    logging.getLogger("telethon").setLevel(logging.INFO)
    logging.getLogger("telethon.network.mtprotosender").setLevel(logging.WARNING)
    logging.getLogger("telethon.extensions.messagepacker").setLevel(logging.WARNING)
    logging.getLogger("telethon.client.updates").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)