import sqlite3

# Caminho do banco de dados
db_path = '../database/sinais.db'

# Função para conectar e buscar as ordens
def consultar_ordens():
    # Conectar ao banco
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Consulta básica: pegar todas as ordens
    cursor.execute('SELECT id, data_hora, par, tipo_ordem, entry_min, entry_max, stoploss, flag_executado FROM sinais ORDER BY id DESC')

    ordens = cursor.fetchall()

    # Fechar conexão
    conn.close()

    # Exibir resultados
    for ordem in ordens:
        print(f"ID: {ordem[0]} | Data: {ordem[1]} | Par: {ordem[2]} | Tipo: {ordem[3]} | Entrada: {ordem[4]}-{ordem[5]} | Stoploss: {ordem[6]} | Executado: {'Sim' if ordem[7] else 'Não'}")

if __name__ == "__main__":
    consultar_ordens()
