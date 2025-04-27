import sqlite3
import os

# Caminho do novo banco
db_path = 'database/sinais_novo.db'

def ler_sinais():
    if not os.path.exists(db_path):
        print("❌ Banco de dados não encontrado.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, data_hora, par, tipo_ordem, margem, alavancagem,
               entrada_inferior, entrada_superior, tp1, tp2, tp3, tp4,
               stoploss, flag_executado
        FROM sinais
        ORDER BY id DESC
    ''')
    sinais = cursor.fetchall()
    conn.close()

    for sinal in sinais:
        print(f"ID: {sinal[0]}")
        print(f"Data/Hora: {sinal[1]}")
        print(f"Par: {sinal[2]} | Tipo: {sinal[3]}")
        print(f"Margem: {sinal[4]} | Alavancagem: {sinal[5]}")
        print(f"Entrada: {sinal[6]} - {sinal[7]}")
        print(f"TP1: {sinal[8]} | TP2: {sinal[9]} | TP3: {sinal[10]} | TP4: {sinal[11]}")
        print(f"StopLoss: {sinal[12]}")
        print(f"Executado: {'Sim' if sinal[13] else 'Não'}")
        print("-" * 60)

if __name__ == '__main__':
    ler_sinais()
