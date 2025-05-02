import os
import psycopg2

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
                SELECT id, par, tipo_ordem, sl, tp, margem, alavancagem
                FROM sinais
                WHERE flag_ordem_enviada = false
                ORDER BY id ASC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "par": row[1],
                    "tipo_ordem": row[2],
                    "sl": row[3],
                    "tp": row[4],
                    "margem": row[8],
                    "alavancagem": row[9]
                }

def buscar_sinal_para_be():
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, order_id, entry_price, tipo_ordem, par
                FROM sinais
                WHERE flag_ordem_enviada = true AND order_id != 0 AND ativar_be = true
                ORDER BY id ASC
                LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                return {
                    "id": row[0],
                    "order_id": row[1],
                    "entry_price": row[2],
                    "tipo_ordem": row[3],
                    "par": row[4]
                }

def incrementar_retry_be(id_sinal):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sinais SET retry_be_send = retry_be_send + 1 WHERE id = %s", (id_sinal,))
            conn.commit()

def incrementar_retry_order(id_sinal):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sinais SET retry_order_send = retry_order_send + 1 WHERE id = %s", (id_sinal,))
            conn.commit()

def marcar_be_executado(id_sinal, entry_price):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sinais
                SET ativar_be = false, sl = %(sl)s
                WHERE id = %(id_sinal)s
                """,
                {"preco": entry_price, "id_sinal": id_sinal}                
            )
            conn.commit()

def marcar_ordem_enviada(id_sinal, entry_price, order_id):
    with conectar_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sinais
                SET flag_ordem_enviada = true, entry_price = %(preco)s, order_id=%(order_id)s
                WHERE id = %(id_sinal)s
                """,
                {"preco": entry_price, "id_sinal": id_sinal, "order_id": order_id}                
            )
            conn.commit()