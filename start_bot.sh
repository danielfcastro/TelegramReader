#!/bin/sh
. venv/bin/activate
python3 start_all.py --testnet >> logs/tradebot.log 2>&1