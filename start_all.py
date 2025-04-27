import threading
import subprocess
import os

def iniciar_telegram_reader():
    os.system('python TelegramReader.py')

def iniciar_trade_executor():
    os.system('python TradeExecutor.py')

if __name__ == "__main__":
    print("🚀 Iniciando Telegram Signal Reader e Trade Executor...")

    thread_reader = threading.Thread(target=iniciar_telegram_reader)
    thread_executor = threading.Thread(target=iniciar_trade_executor)

    thread_reader.start()
    thread_executor.start()

    thread_reader.join()
    thread_executor.join()
