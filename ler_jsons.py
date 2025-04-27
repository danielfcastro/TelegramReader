import os
import json
import csv

# Pasta onde ficam os JSONs
jsons_path = 'logs/jsons/'

def carregar_jsons():
    sinais = []
    monitoramentos = []
    if not os.path.exists(jsons_path):
        print("❌ Pasta logs/jsons/ não encontrada.")
        return sinais, monitoramentos

    arquivos = [f for f in os.listdir(jsons_path) if f.endswith('.json')]

    for arquivo in arquivos:
        caminho = os.path.join(jsons_path, arquivo)
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            if dados.get('tipo') == 'sinal':
                sinais.append(dados)
            else:
                monitoramentos.append(dados)

    return sinais, monitoramentos

def gerar_csv(sinais, monitoramentos):
    if not sinais and not monitoramentos:
        print("Nenhum dado para exportar.")
        return

    if not os.path.exists('exports'):
        os.makedirs('exports')

    with open('exports/sinais.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['DataHora', 'Par', 'TipoOrdem', 'Margem', 'Alavancagem', 'EntradaInf', 'EntradaSup', 'TP1', 'TP2', 'TP3', 'TP4', 'StopLoss'])
        for sinal in sinais:
            writer.writerow([
                sinal.get('data_hora', ''),
                sinal.get('par', ''),
                sinal.get('tipo_ordem', ''),
                sinal.get('margem', ''),
                sinal.get('alavancagem', ''),
                sinal.get('entrada_inferior', ''),
                sinal.get('entrada_superior', ''),
                sinal.get('tp1', ''),
                sinal.get('tp2', ''),
                sinal.get('tp3', ''),
                sinal.get('tp4', ''),
                sinal.get('stoploss', '')
            ])

    with open('exports/monitoramentos.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Par', 'PreçoAtual', 'Profit%', 'Spent', 'Instruction', 'TargetDone'])
        for mon in monitoramentos:
            writer.writerow([
                mon.get('pair', ''),
                mon.get('price', ''),
                mon.get('profit', ''),
                mon.get('spent', ''),
                mon.get('instruction', ''),
                mon.get('target_done', '')
            ])

    print("✅ Arquivos CSV gerados na pasta 'exports/'.")

def main():
    sinais, monitoramentos = carregar_jsons()

    print("\nResumo de Mensagens Capturadas")
    print("------------------------------")
    print(f"✅ {len(sinais)} sinais de entrada")
    print(f"✅ {len(monitoramentos)} mensagens de monitoramento\n")

    if sinais:
        exemplo = sinais[0]
        print("Exemplo de Sinal:")
        print(f"- Par: {exemplo.get('par')}")
        print(f"- Entrada: {exemplo.get('entrada_inferior')} - {exemplo.get('entrada_superior')}")
        print(f"- TP1: {exemplo.get('tp1')}")
        print(f"- StopLoss: {exemplo.get('stoploss')}")
        print()

    if monitoramentos:
        exemplo = monitoramentos[0]
        print("Exemplo de Monitoramento:")
        print(f"- Par: {exemplo.get('pair')}")
        print(f"- Price atual: {exemplo.get('price')}")
        print(f"- Profit: {exemplo.get('profit')}%")
        print(f"- Instruction: {exemplo.get('instruction')}")
        print()

    opcao = input("Deseja exportar para CSV? [s/n]: ").strip().lower()
    if opcao == 's':
        gerar_csv(sinais, monitoramentos)

if __name__ == '__main__':
    main()
