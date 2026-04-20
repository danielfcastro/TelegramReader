import logging
import os
import time
from flask import Flask, request, jsonify

# Tentativa de importação do módulo de banco de dados
try:
    import database
except ImportError:
    database = None
    logging.warning("⚠️ - Módulo 'database' não encontrado. Algumas funcionalidades podem estar limitadas.")

from message.mensagem_sinal import MensagemSinal
from message.mensagem_tp import MensagemTP
from integration.BingXBroker import BingXBroker
from utils import ajustar_quantidade
from log.logger_config import configurar_logging

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
proporcoes = [0.1, 0.2, 0.5, 0.2]
REQUIRED_MARGIN_TYPE = "CROSSED"

configurar_logging()

app = Flask(__name__)
broker = BingXBroker()

@app.route('/trade', methods=['POST'])
def execute_trade():
    """
    Endpoint para processar novos sinais de trade (POST /trade).
    Divide o sinal em 4 ordens separadas com proporções específicas.
    """
    try:
        mensagem = request.get_json()
        if not mensagem:
            return jsonify({"sucesso": False, "msg": "JSON inválido ou ausente"}), 400

        logger.info(f"📩 - Requisição de SINAL (POST /trade) recebida")
        msg = MensagemSinal(**mensagem)
        
        # Lógica de execução de sinal (4-way split)
        preco_mercado = broker.obter_preco_mercado(msg.symbol)
        margin_type = broker.verificar_tipo_margem(msg.symbol)
        
        if margin_type == "ERROR":
            return jsonify({"sucesso": False, "msg": f"Erro ao obter margem para {msg.symbol}"}), 500

        if margin_type != REQUIRED_MARGIN_TYPE:
            broker.mudar_tipo_margem(msg.symbol)
            
        saldo = broker.obter_saldo_disponivel()
        trade_percentage = float(os.getenv("TRADE_PERCENTAGE", "3"))
        valor_trade = saldo * (trade_percentage / 100)
        
        quantidade_total = ajustar_quantidade(valor_trade / preco_mercado, step=0.0001)
        
        tps = [msg.tp1, msg.tp2, msg.tp3, msg.tp4]
        quantidade_acumulada = quantidade_total
        sucessos = 0
        detalhes_ordens = []

        for i, proporcao in enumerate(proporcoes):
            if i < len(proporcoes) - 1:
                qtd_proporcional = ajustar_quantidade(quantidade_total * proporcao, step=0.0001)
                quantidade_acumulada -= qtd_proporcional
            else:
                qtd_proporcional = quantidade_acumulada
            
            preco_tp = tps[i]
            logger.info(f"🚀 - Ordem {i+1}/4: {msg.symbol} | Qtd: {qtd_proporcional} | TP: {preco_tp} | SL: {msg.sl}")
            
            _retorno = broker.enviar_ordem_tp_sl(msg, qtd_proporcional, take_profit=preco_tp)
            
            if _retorno["sucesso"]:
                sucessos += 1
                detalhes_ordens.append({"tp": i+1, "order_id": _retorno["order_id"]})
            else:
                logger.error(f"❌ - Erro no TP{i+1}: {_retorno['msg']}")
            
            time.sleep(0.5)

        if sucessos > 0:
            msg_final = f"🏁 - Processamento de sinal concluído. {sucessos}/4 ordens executadas."
            logger.info(msg_final)
            return jsonify({"sucesso": True, "msg": msg_final, "detalhes": detalhes_ordens}), 200
        else:
            return jsonify({"sucesso": False, "msg": "Falha total ao processar sinal"}), 500

    except Exception as e:
        logger.error(f"❌ - Erro em /trade: {e}")
        return jsonify({"sucesso": False, "msg": str(e)}), 500

@app.route('/tp', methods=['PUT'])
def process_tp():
    """
    Endpoint para processar monitoramento de Take Profit (PUT /tp).
    Ajusta Stop Loss ou encerra posição conforme o alvo atingido.
    """
    try:
        mensagem = request.get_json()
        if not mensagem:
            return jsonify({"sucesso": False, "msg": "JSON inválido ou ausente"}), 400

        logger.info(f"📩 - Requisição de TP (PUT /tp) recebida")
        msg = MensagemTP(**mensagem)
        symbol = msg.symbol
        numero_tp = int(msg.tp.replace("TP", ""))

        if not database:
            return jsonify({"sucesso": False, "msg": "Módulo database não configurado"}), 500

        order_id = database.take_profit.tp_ordem_id_mais_nova(symbol)
        if order_id == 0:
            return jsonify({"sucesso": False, "msg": f"Nenhuma ordem encontrada para {symbol}"}), 404

        msg.order_id = order_id
        database.take_profit.tp_atualizar(order_id=msg.order_id, numero_tp=msg.tp, novo_status=2)

        response = broker.get_open_order_info(symbol=symbol, order_id=order_id)
        if not response:
            return jsonify({"sucesso": False, "msg": "Ordem não encontrada na corretora"}), 404

        entry_price = response["data"]["order"]["avgPrice"]
        current_stop_price = response["data"]["order"]["stopLoss"]["stopPrice"]
        current_order_side = response["data"]["order"]["side"]

        stop_price = current_stop_price if numero_tp == 1 else entry_price

        if numero_tp >= 2:
            database.stop_loss.stop_loss_update(order_id=order_id, novo_sl=stop_price)

        if numero_tp < 4:
            quantidade = database.stop_loss.stop_loss_soma_quantidade(order_id)
            sucesso = broker.ajustar_stop_loss(
                symbol=symbol,
                position_side="BOTH",
                quantity=quantidade,
                stop_price=stop_price,
                order_id=order_id,
                current_order_side=current_order_side
            )
            if not sucesso:
                database.take_profit.tp_atualizar(order_id=order_id, numero_tp=numero_tp, novo_status=1)
                return jsonify({"sucesso": False, "msg": "Falha ao ajustar SL"}), 500
            else:
                return jsonify({"sucesso": True, "msg": f"TP{numero_tp} processado"}), 200
        else:
            # TP4 - Encerramento
            for i in range(1, 5):
                database.take_profit.tp_atualizar(order_id=order_id, numero_tp=i, novo_status=2)
            time.sleep(1.5)
            broker.cancela_ordem_tp(symbol=symbol)
            broker.cancela_ordem_sl(symbol=symbol)
            broker.fecha_ordem_mercado(symbol=symbol)
            return jsonify({"sucesso": True, "msg": "TP4 processado e posição encerrada"}), 200

    except Exception as e:
        logger.error(f"❌ - Erro em /tp: {e}")
        return jsonify({"sucesso": False, "msg": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT_EXECUTOR", 8001))
    logger.info(f"✅ - TradeExecutor Unificado iniciado na porta {port}")
    app.run(host='0.0.0.0', port=port)
