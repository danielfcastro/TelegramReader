# logger_config.py
import logging
import os

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[92m',   # verde
        'INFO': '\033[0m',     # branco (default)
        'WARNING': '\033[93m', # amarelo
        'ERROR': '\033[91m',   # vermelho
        'CRITICAL': '\033[95m' # magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"

def configurar_logging(log_level=logging.DEBUG, log_dir='logs', log_file='app.log'):
    os.makedirs(log_dir, exist_ok=True)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(
        "%(asctime)s -  %(levelname)s - %(name)s - %(funcName)s - %(message)s"
    ))

    file_handler = logging.FileHandler(os.path.join(log_dir, log_file), encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s -  %(levelname)s - %(name)s - %(funcName)s - %(message)s"
    ))

    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler]
    )

    # Ajuste para loggers
    logging.getLogger("start_all").setLevel(logging.INFO)
    logging.getLogger("TelegramReader").setLevel(logging.DEBUG)
    logging.getLogger("TradeExecutor").setLevel(logging.DEBUG)
    logging.getLogger("BingXBroker").setLevel(logging.DEBUG)
    logging.getLogger("util").setLevel(logging.DEBUG)

    logging.getLogger("telethon").setLevel(logging.INFO)
    logging.getLogger("telethon.network.mtprotosender").setLevel(logging.WARNING)
    logging.getLogger("telethon.extensions.messagepacker").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)