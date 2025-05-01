import os
import time
import threading
import psycopg2
from dotenv import load_dotenv
from integration.bybit_trading import enviar_ordem_sem_tp_sl, configurar_take_profits, configurar_stop_loss

load_dotenv()

def conectar_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def buscar_sinal_execucao():
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, par, tipo_ordem, stoploss, tp1, tp2, tp3, tp4
                FROM sinais
                WHERE flag_ordem_enviada = 0
                ORDER BY id ASC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "pair": row[1],
                    "type": row[2],
                    "stoploss": row[3],
                    "tp1": row[4],
                    "tp2": row[5],
                    "tp3": row[6],
                    "tp4": row[7]
                }

def buscar_sinal_config():
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, par, tipo_ordem, stoploss, tp1, tp2, tp3, tp4, 
                       flag_tp_configurado, flag_sl_configurado 
                FROM sinais
                WHERE flag_ordem_enviada = 1 
                  AND ((flag_tp_configurado = false AND tentativas_tp <3)
                        OR (flag_sl_configurado = false AND tentativas_sl <3))
                ORDER BY id ASC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "pair": row[1],
                    "type": row[2],
                    "stoploss": row[3],
                    "tp1": row[4],
                    "tp2": row[5],
                    "tp3": row[6],
                    "tp4": row[7],
                    "flag_tp_configurado": row[8],
                    "flag_sl_configurado": row[9]
                }

def incrementar_tentativas_tp(id_sinal):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sinais
                SET tentativas_tp = tentativas_tp + 1
                WHERE id = %s
            """, (id_sinal,))
            conn.commit()

def incrementar_tentativas_sl(id_sinal):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sinais
                SET tentativas_sl = tentativas_sl + 1
                WHERE id = %s
            """, (id_sinal,))
            conn.commit()


def marcar_ordem_enviada(sinal_id):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sinais SET flag_ordem_enviada = 1 WHERE id = %s
            """, (sinal_id,))
            conn.commit()

def marcar_tp_configurado(id_sinal):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sinais SET flag_tp_configurado = TRUE WHERE id = %s", (id_sinal,))
            conn.commit()

def marcar_sl_configurado(id_sinal):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sinais SET flag_sl_configurado = TRUE WHERE id = %s", (id_sinal,))
            conn.commit()

def deletar_sinal(sinal_id):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sinais WHERE id = %s", (sinal_id,))
            conn.commit()

def loop_execucao_ordens():
    while True:
        try:
            sinal = buscar_sinal_execucao()
            if sinal:
                print(f"🟡 Enviando ordem para {sinal['pair']}")
                sucesso = enviar_ordem_sem_tp_sl(sinal)
                if sucesso:
                    marcar_ordem_enviada(sinal["id"])
            time.sleep(5)
        except Exception as e:
            print("❌ Erro no loop de execução de ordens:", e)

def loop_configuracao_tp_sl():
    while True:
        try:
            sinal = buscar_sinal_config()
            if sinal:
                print(f"⚙️ Configurando TP/SL para {sinal['pair']}")

                if not sinal["flag_tp_configurado"]:
                    if configurar_take_profits(sinal):
                        marcar_tp_configurado(sinal["id"])
                    else:
                        incrementar_tentativas_tp(sinal["id"])

                if not sinal["flag_sl_configurado"]:
                    if configurar_stop_loss(sinal):
                        marcar_sl_configurado(sinal["id"])
                    else:
                        incrementar_tentativas_sl(sinal["id"])
        except Exception as e:
            print("❌ Erro no loop de configuração de TP/SL:", e)
        time.sleep(5)


if __name__ == "__main__":
    print("🚀 Executor iniciado com loops paralelos.")

    t1 = threading.Thread(target=loop_execucao_ordens, daemon=True)
    t2 = threading.Thread(target=loop_configuracao_tp_sl, daemon=True)

    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Execução do bot interrompida pelo usuário.")
