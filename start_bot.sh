#!/bin/sh
cd /root/TelegramReader
. venv/bin/activate
python3 start_all.py --mainnet >> /var/log/tradebot.log 2>&1