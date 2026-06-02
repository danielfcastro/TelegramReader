import logging
import os
import json
import time
from flask import Flask, request, jsonify
import atexit

# Global counters for outcomes (runtime only, logged to app.log)
# trade_successful: number of trades where at least one order was created successfully
trade_successful = 0

# Módulo de banco de dados foi removido (agora 100% Stateless)

from message.mensagem_sinal import MensagemSinal
from message.mensagem_tp import MensagemTP
from integration.BingXBroker import BingXBroker
from utils import ajustar_quantidade
from log.logger_config import configurar_logging
from analise_tecnica import analisar

logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
# 5 ordens: 4 com TP fixo (10%+20%+50%+10%) + 1 sem TP (10% rastreado pelo Trailing Stop)
proporcoes = [0.1, 0.2, 0.5, 0.1, 0.1]
REQUIRED_MARGIN_TYPE = "CROSSED"

configurar_logging()

app = Flask(__name__)
broker = BingXBroker()

# Register a shutdown hook to log final TP/SL/Trade counts from persistent analytics
def _log_final_counts():
    import json
    import os
    analytics_file = "trade_analytics.json"
    tp_val, sl_val, ts_val = 0, 0, 0
    if os.path.exists(analytics_file):
        try:
            with open(analytics_file, "r") as f:
                data = json.load(f)
                tp_val = data.get("tp_hits", 0)
                sl_val = data.get("sl_hits", 0)
                ts_val = data.get("trailing_hits", 0)
        except Exception:
            pass
    total = tp_val + sl_val + ts_val
    success_rate = 0.0
    if total > 0:
        success_rate = ((tp_val + ts_val) / total) * 100.0
    logger.info(f"📊 - Resumo final de performance no encerramento: A (TP): {tp_val} | B (SL): {sl_val} | C (TS): {ts_val} | Total: {total} | Success Rate: {success_rate:.2f}%")
atexit.register(_log_final_counts)

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
        use_technical_analysis = os.getenv("USE_TECHNICAL_ANALYSIS", "true").lower() == "true"
        
        if use_technical_analysis:
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
        else:
            logger.info(f"⚡ - Análise Técnica desabilitada via USE_TECHNICAL_ANALYSIS. Aprovando sinal {msg.symbol} diretamente.")
        
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

        # 5 TPs: os 4 primeiros têm preço fixo, o 5º não tem TP (rastreado pelo Trailing Stop)
        tps = [msg.tp1, msg.tp2, msg.tp3, msg.tp4, None]
        sucessos = 0
        tp_count = 0  # Conta apenas ordens COM TP fixo (para o PositionMonitor)
        detalhes_ordens = []

        for i, proporcao in enumerate(proporcoes):
            qtd_proporcional = ajustar_quantidade(quantidade_total * proporcao, step=0.0001)
            preco_tp = tps[i]

            if preco_tp is not None:
                logger.info(f"🚀 - Ordem {i+1}/5: {msg.symbol} | Qtd: {qtd_proporcional} | TP: {preco_tp} | SL: {msg.sl}")
            else:
                logger.info(f"🚀 - Ordem {i+1}/5: {msg.symbol} | Qtd: {qtd_proporcional} | SL: {msg.sl} | [Sem TP fixo → Trailing Stop]")

            _retorno = broker.enviar_ordem_tp_sl(msg, qtd_proporcional, take_profit=preco_tp)

            if _retorno["sucesso"]:
                sucessos += 1
                if preco_tp is not None:
                    tp_count += 1
                detalhes_ordens.append({"ordem": i+1, "order_id": _retorno["order_id"], "tp": preco_tp})
            else:
                logger.error(f"❌ - Erro na Ordem {i+1}: {_retorno['msg']}")

            time.sleep(0.5)

        if sucessos > 0:
            # Increment successful trade counter (at least one order succeeded)
            global trade_successful
            trade_successful += 1
            logger.info(f"✅ - Trade bem sucedido registrado; total trades bem sucedidos: {trade_successful}")
            # Salva a contagem de TPs com preço fixo (não o total de ordens)
            # O PositionMonitor usa esse valor para detectar quando acionar BE/TS
            try:
                import json
                state_file = "active_trades.json"
                state = {}
                if os.path.exists(state_file):
                    with open(state_file, "r") as f:
                        state = json.load(f)
                state[msg.symbol] = tp_count  # ex: 4 (não 5)
                with open(state_file, "w") as f:
                    json.dump(state, f)
            except Exception as e:
                logger.error(f"Erro ao salvar state em active_trades.json: {e}")

            msg_final = f"🏁 - Processamento concluído. {sucessos}/5 ordens executadas ({tp_count} com TP fixo + 1 para Trailing Stop)."
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

        from utils import registrar_saida_trade

        # Se 'data' for vazio, não há posição aberta → possivelmente SL ou TS hit
        if not pos_res.get("data"):
            # Carrega o estado salvo para saber se ainda havia TP(s) ativos
            try:
                with open('active_trades.json', 'r') as f:
                    state = json.load(f)
            except Exception:
                state = {}
            if state.get(symbol, 0) > 0:
                ts_ativo = state.get(f"{symbol}_ts_active", False)
                if ts_ativo:
                    registrar_saida_trade('TS', symbol)
                else:
                    registrar_saida_trade('SL', symbol)
                state.pop(symbol, None)
                state.pop(f"{symbol}_ts_active", None)
                try:
                    with open('active_trades.json', 'w') as f:
                        json.dump(state, f)
                except Exception:
                    pass
            logger.warning(f"⚠️ - Nenhuma posição aberta para {symbol}. Ignorando {msg.tp}.")
            return jsonify({"sucesso": True, "msg": "Nenhuma posição aberta"}), 200

        # Encontra a posição ativa no modo One-Way
        posicao = next((p for p in pos_res["data"] if float(p["positionAmt"]) != 0), None)
        if not posicao:
            logger.warning(f"⚠️ - Nenhuma posição ativa com volume encontrada para {symbol} ao processar {msg.tp}.")
            return jsonify({"sucesso": True, "msg": "Nenhuma posição com volume"}), 200

        entry_price = float(posicao["avgPrice"])
        quantidade = abs(float(posicao["positionAmt"]))
        position_side = posicao.get("positionSide", "LONG" if float(posicao["positionAmt"]) > 0 else "SHORT")

        side_sl = "SELL" if position_side == "LONG" else "BUY"

        # Atualiza os contadores baseando-se nos TPs atingidos e atualiza o active_trades.json
        try:
            with open('active_trades.json', 'r') as f:
                state = json.load(f)
        except Exception:
            state = {}

        expected = state.get(symbol, 4)
        target_remaining = 4 - numero_tp
        if expected > target_remaining:
            diff = expected - target_remaining
            for _ in range(diff):
                registrar_saida_trade('TP', symbol)
            state[symbol] = target_remaining
            try:
                with open('active_trades.json', 'w') as f:
                    json.dump(state, f)
            except Exception as e:
                logger.error(f"Erro ao salvar active_trades em /tp: {e}")

        if 1 <= numero_tp <= 3:
            logger.info(f"🎯 - TP{numero_tp} atingido para {symbol}. Verificando Break Even...")

            ordens_res_sl = broker.obter_ordens_abertas(symbol)
            sl_orders, ts_orders = [], []
            if ordens_res_sl and ordens_res_sl.get("code") == 0:
                ordens_abertas = ordens_res_sl.get("data", {}).get("orders", [])
                sl_orders = [o for o in ordens_abertas if o["type"] == "STOP_MARKET"]
                ts_orders = [o for o in ordens_abertas if o["type"] in ["TRAILING_STOP_MARKET", "TRAILING_TP_SL"]]

            if len(ts_orders) > 0:
                logger.info(f"ℹ️ - {symbol}: Trailing Stop já ativo. Ignorando BE para TP{numero_tp}.")
                return jsonify({"sucesso": True, "msg": f"TP{numero_tp}: Trailing Stop já ativo, BE ignorado"}), 200

            needs_be = True
            if len(sl_orders) > 0:
                current_sl = float(sl_orders[0].get("stopPrice", 0))
                if abs(current_sl - entry_price) / entry_price <= 0.001:
                    needs_be = False
                    logger.info(f"ℹ️ - {symbol}: SL já está no Break Even para TP{numero_tp}.")

            if needs_be:
                broker.cancela_ordem_sl(symbol)
                time.sleep(0.5)
                ret_sl = broker.enviar_ordem_sl(symbol, side_sl, quantidade, entry_price)
                if ret_sl.get("code") == 0:
                    logger.info(f"✅ - SL movido para Break Even ({entry_price}) para {symbol} no TP{numero_tp}")
                    return jsonify({"sucesso": True, "msg": f"TP{numero_tp} processado e Break Even ativado"}), 200
                else:
                    logger.error(f"❌ - Falha ao ajustar SL para {symbol}: {ret_sl.get('msg')}")
                    return jsonify({"sucesso": False, "msg": "Falha ao ajustar SL"}), 500

            return jsonify({"sucesso": True, "msg": f"TP{numero_tp} processado (Break Even já ativo)"}), 200

        elif numero_tp == 4:
            logger.info(f"🎯 - TP4 atingido para {symbol}. Ativando Trailing Stop para os 10% restantes...")
            broker.cancela_ordem_sl(symbol)
            time.sleep(0.5)
            callback_rate = float(os.getenv("TRAILING_STOP_RATE", "1.5"))
            ret_ts = broker.enviar_trailing_stop(symbol, side_sl, quantidade, callback_rate=callback_rate)
            if ret_ts.get("code") == 0:
                logger.info(f"✅ - Trailing Stop ativado para {symbol} com callback de {callback_rate}%")
                
                # Marca o trailing stop como ativo
                try:
                    with open('active_trades.json', 'r') as f:
                        state = json.load(f)
                except Exception:
                    state = {}
                state[f"{symbol}_ts_active"] = True
                try:
                    with open('active_trades.json', 'w') as f:
                        json.dump(state, f)
                except Exception:
                    pass

                return jsonify({"sucesso": True, "msg": "TP4 processado e Trailing Stop ativado"}), 200
            else:
                logger.error(f"❌ - Falha ao criar Trailing Stop para {symbol}: {ret_ts.get('msg')}")
                return jsonify({"sucesso": False, "msg": "Falha ao ativar Trailing Stop"}), 500

        else:
            logger.info(f"🎯 - TP{numero_tp} para {symbol}: posição já gerenciada pelo Trailing Stop.")
            return jsonify({"sucesso": True, "msg": f"TP{numero_tp}: Trailing Stop em curso"}), 200

    except Exception as e:
        logger.error(f"❌ - Erro em /tp: {e}")
        return jsonify({"sucesso": False, "msg": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT_EXECUTOR", 8001))
    logger.info(f"✅ - TradeExecutor Unificado iniciado na porta {port}")
    app.run(host='0.0.0.0', port=port)
