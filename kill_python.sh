#!/bin/sh

echo "🔍 Procurando processos Python com conexões ativas..."

PIDS=$(netstat -putona 2>/dev/null | grep python | awk '{print $7}' | cut -d/ -f1 | sort -u)

if [ -z "$PIDS" ]; then
  echo "✅ Nenhum processo Python com conexão ativa encontrado."
  exit 0
fi

for pid in $PIDS; do
  if ps -p "$pid" > /dev/null; then
    echo "🔪 Matando processo Python com PID: $pid"
    kill -9 "$pid"
  fi
done

echo "✅ Todos os processos Python com conexões encerrados."
