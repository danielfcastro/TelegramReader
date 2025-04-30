from flask import Flask, render_template
import psycopg2
import psycopg2.extras
import os

def carregar_config(path):
    config = {}
    if not os.path.exists(path):
        print(f"Arquivo de configuração {path} não encontrado.")
        exit(1)
    with open(path, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith('#'):
                chave, valor = linha.split('=', 1)
                config[chave.strip()] = valor.strip()
    return config

temp_config = carregar_config('../config.properties')
db_host = temp_config.get('db_host', 'localhost')
db_port = int(temp_config.get('db_port', 5432))
db_name = temp_config.get('db_name', '')
db_user = temp_config.get('db_user', '')
db_password = temp_config.get('db_password', '')

app = Flask(__name__)

def obter_sinais():
    conn = psycopg2.connect(
        host=db_host, port=db_port,
        dbname=db_name, user=db_user, password=db_password
    )
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT * FROM sinais ORDER BY data_hora DESC')
    sinais = cursor.fetchall()
    conn.close()
    return sinais

def obter_monitoramentos():
    conn = psycopg2.connect(
        host=db_host, port=db_port,
        dbname=db_name, user=db_user, password=db_password
    )
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('SELECT * FROM monitoramentos ORDER BY data_hora DESC')
    monitoramentos = cursor.fetchall()
    conn.close()
    return monitoramentos

@app.route('/')
def dashboard():
    sinais = obter_sinais()
    monitoramentos = obter_monitoramentos()
    return render_template('dashboard.html', sinais=sinais, monitoramentos=monitoramentos)

if __name__ == '__main__':
    app.run(debug=True)
