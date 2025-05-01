import os
import time
import psycopg2
from dotenv import load_dotenv
from integration.bybit_trading import abrir_ordem_com_tps, set_break_even

load_dotenv()

def conectar_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def buscar_sinais_nao_executados():
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, par, tipo_ordem, entrada_inferior, entrada_superior,
                       tp1, tp2, tp3, tp4, stoploss
                FROM sinais
                WHERE flag_executado = 0
                ORDER BY data_hora ASC
                LIMIT 1
            """)
            return cur.fetchone()

def marcar_sinal_como_executado(sinal_id):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sinais
                SET flag_executado = 1
                WHERE id = %s
            """, (sinal_id,))
            conn.commit()

def buscar_break_even():
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, par FROM break_even
                WHERE flag_executado = 0
                ORDER BY data_hora ASC
                LIMIT 1
            """)
            return cur.fetchone()

def marcar_break_even_executado(break_even_id):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE break_even
                SET flag_executado = 1
                WHERE id = %s
            """, (break_even_id,))
            conn.commit()

def loop_principal():
    print("🚀 Iniciando loop de execução de sinais...")
    while True:
        try:
            sinal = buscar_sinais_nao_executados()
            if sinal:
                print(f"🟡 Executando sinal: {sinal[1]} ({sinal[2]})")
                sinal_dict = {
                    "pair": sinal[1],
                    "type": sinal[2],
                    "entry_low": float(sinal[3]),
                    "entry_high": float(sinal[4]),
                    "tp1": float(sinal[5]),
                    "tp2": float(sinal[6]),
                    "tp3": float(sinal[7]),
                    "tp4": float(sinal[8]),
                    "stoploss": float(sinal[9])
                }
                sucesso = abrir_ordem_com_tps(sinal_dict)
                if sucesso:
                    marcar_sinal_como_executado(sinal[0])
                else:
                    print(f"⚠️ Ordem para {sinal[1]} não foi executada com sucesso. Não será marcada como executada.")                

            be = buscar_break_even()
            if be:
                print(f"🟠 Ajustando break-even para: {be[1]}")
                set_break_even(be[1].replace("/", ""))
                marcar_break_even_executado(be[0])

        except Exception as e:
            print(f"❌ Erro no loop principal: {e}")

        time.sleep(5)

if __name__ == "__main__":
    loop_principal()
