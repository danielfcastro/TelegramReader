#!/bin/sh
cd /root/TelegramReader
. venv/bin/activate
setsid python3 start_all.py --testnet >> /var/log/tradebot.log 2>&1 &
echo $! > /run/tradebot.pid