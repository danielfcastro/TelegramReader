from flask import Flask, render_template
import sqlite3
import os

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '../database/sinais.db')

def obter_sinais():
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, data_hora, par, tipo_ordem, entry_min, entry_max, stoploss, flag_executado FROM sinais ORDER BY id DESC LIMIT 50')
    sinais = cursor.fetchall()
    conn.close()
    return sinais

@app.route('/')
def dashboard():
    sinais = obter_sinais()
    return render_template('dashboard.html', sinais=sinais)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
