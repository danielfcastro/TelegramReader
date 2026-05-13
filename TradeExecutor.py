import logging
import os
import time
from flask import Flask, request, jsonify

# Módulo de banco de dados foi removido (agora 100% Stateless)

from message.mensagem_sinal import MensagemSinal
from message.mensagem_tp import MensagemTP
from integration.BingXBroker import BingXBroker
from utils import ajustar_quantidade
from log.logger_config import configurar_logging
from analise_tecnica import analisar

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
        
        # Análise Técnica antes de executar a ordem
        logger.info(f"🔍 - Analisando tendência para {msg.symbol}...")
        resultado_analise = analisar(msg.symbol, msg.tipo_ordem)
        
        if not resultado_analise.get("confluencia", False):
            motivos = " | ".join(resultado_analise.get("motivo_rejeicao", []))
            logger.warning(f"🚫 - Sinal rejeitado pela Análise Técnica: {motivos}")
            return jsonify({
                "sucesso": False,
                "msg": f"Sinal contra a tendência. Motivo: {motivos}",
                "detalhes": resultado_analise
            }), 200
        
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
    Ajusta Stop Loss ou encerra posição conforme o alvo atingido (Stateless).
    """
    try:
        mensagem = request.get_json()
        if not mensagem:
            return jsonify({"sucesso": False, "msg": "JSON inválido ou ausente"}), 400

        logger.info(f"📩 - Requisição de TP (PUT /tp) recebida")
        msg = MensagemTP(**mensagem)
        symbol = msg.symbol
        numero_tp = int(msg.tp.replace("TP", ""))

        pos_res = broker.obter_posicao(symbol)
        if not pos_res or pos_res.get("code") != 0:
            logger.error(f"❌ - Erro ao consultar posição para {symbol} na corretora: {pos_res}")
            return jsonify({"sucesso": False, "msg": "Erro na consulta de posição"}), 500

        # Se 'data' for vazio, não há posição aberta
        if not pos_res.get("data"):
            logger.warning(f"⚠️ - Nenhuma posição aberta para {symbol}. Ignorando {msg.tp}.")
            return jsonify({"sucesso": True, "msg": "Nenhuma posição aberta"}), 200

        # Encontra a posição ativa no modo One-Way
        posicao = next((p for p in pos_res["data"] if float(p["positionAmt"]) != 0), None)
        if not posicao:
            logger.warning(f"⚠️ - Nenhuma posição ativa com volume encontrada para {symbol} ao processar {msg.tp}.")
            return jsonify({"sucesso": True, "msg": "Nenhuma posição com volume"}), 200

        entry_price = float(posicao["avgPrice"])
        quantidade = abs(float(posicao["positionAmt"]))
        position_side = "LONG" if float(posicao["positionAmt"]) > 0 else "SHORT"

        if numero_tp < 4:
            if numero_tp == 3:
                logger.info(f"🎯 - TP3 atingido para {symbol}. Ativando Trailing Stop...")
                side_sl = "SELL" if position_side == "LONG" else "BUY"
                broker.cancela_ordem_sl(symbol)
                time.sleep(0.5)
                
                # Por padrão, trailing stop com callback de 1.5%
                callback_rate = float(os.getenv("TRAILING_STOP_RATE", "1.5"))
                ret_ts = broker.enviar_trailing_stop(symbol, side_sl, quantidade, callback_rate=callback_rate)
                
                if ret_ts.get("code") == 0:
                    logger.info(f"✅ - Trailing Stop ativado para {symbol} com callback de {callback_rate}%")
                    return jsonify({"sucesso": True, "msg": f"TP3 processado e Trailing Stop ativado"}), 200
                else:
                    logger.error(f"❌ - Falha ao criar Trailing Stop para {symbol}: {ret_ts.get('msg')}")
                    return jsonify({"sucesso": False, "msg": "Falha ao ativar Trailing Stop"}), 500

            elif numero_tp == 2:
                logger.info(f"🎯 - TP2 atingido para {symbol}. Movendo SL para Break Even...")
                # O SL é o inverso da posição
                side_sl = "SELL" if position_side == "LONG" else "BUY"

                broker.cancela_ordem_sl(symbol)
                time.sleep(0.5)

                ret_sl = broker.enviar_ordem_sl(symbol, side_sl, quantidade, entry_price)
                if ret_sl.get("code") == 0:
                    logger.info(f"✅ - SL movido com sucesso para {entry_price} (Break Even) para {symbol}")
                    return jsonify({"sucesso": True, "msg": f"TP{numero_tp} processado e Break Even ativado"}), 200
                else:
                    logger.error(f"❌ - Falha ao criar novo SL para {symbol}: {ret_sl.get('msg')}")
                    return jsonify({"sucesso": False, "msg": "Falha ao ajustar SL"}), 500

            return jsonify({"sucesso": True, "msg": f"TP{numero_tp} ignorado para ajuste de SL/Trailing Stop"}), 200

        else:
            # TP4 - Encerramento de todas as posições daquele símbolo
            logger.info(f"🎯 - TP4 atingido para {symbol}. Encerrando posição e cancelando ordens...")
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
