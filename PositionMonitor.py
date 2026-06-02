import time
import os
import logging
from log.logger_config import configurar_logging
from integration.BingXBroker import BingXBroker

configurar_logging()
logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0])
broker = BingXBroker()

def monitorar_posicoes():
    """
    Roda continuamente para verificar posições e ordens ativas.
    Infere as execuções de TP pela quantidade de ordens TAKE_PROFIT_MARKET
    restantes e ajusta o Stop Loss (Break Even e Trailing Stop).
    """
    logger.info("👀 - PositionMonitor iniciado.")
    
    while True:
        try:
            # 1. Obtém todas as posições abertas
            pos_res = broker._send_request("GET", "/openApi/swap/v2/user/positions", {})
            if not pos_res or pos_res.get("code") != 0:
                time.sleep(15)
                continue

            posicoes_ativas = [p for p in pos_res.get("data", []) if float(p["positionAmt"]) != 0]
            simbolos_ativos_nomes = [pos["symbol"] for pos in posicoes_ativas]

            # 2. Carrega active_trades.json
            state_file = "active_trades.json"
            state = {}
            if os.path.exists(state_file):
                try:
                    with open(state_file, "r") as f:
                        state = json.load(f)
                except Exception:
                    pass

            from utils import registrar_saida_trade
            import json

            # 3. Verifica trades que fecharam (estavam no active_trades mas não estão mais ativos na corretora)
            state_modificado = False
            for k in list(state.keys()):
                if not k.endswith("-USDT"):
                    continue
                if k not in simbolos_ativos_nomes:
                    # Trade fechou!
                    ts_ativo = state.get(f"{k}_ts_active", False)
                    if ts_ativo:
                        registrar_saida_trade('TS', k)
                    else:
                        registrar_saida_trade('SL', k)
                    
                    # Remove o símbolo e sua chave auxiliar
                    state.pop(k, None)
                    state.pop(f"{k}_ts_active", None)
                    state_modificado = True

            if state_modificado:
                try:
                    with open(state_file, "w") as f:
                        json.dump(state, f)
                except Exception as e:
                    logger.error(f"Erro ao salvar state em active_trades.json no monitor: {e}")

            for pos in posicoes_ativas:
                symbol = pos["symbol"]
                avg_price = float(pos["avgPrice"])
                quantidade = abs(float(pos["positionAmt"]))
                position_side = pos.get("positionSide", "LONG" if float(pos["positionAmt"]) > 0 else "SHORT")
                side_sl = "SELL" if position_side == "LONG" else "BUY"

                # Obtém todas as ordens abertas para o símbolo
                ordens_res = broker.obter_ordens_abertas(symbol)
                if not ordens_res or ordens_res.get("code") != 0:
                    continue
                
                ordens = ordens_res.get("data", {}).get("orders", [])
                
                # Conta TPs
                tps = [o for o in ordens if o["type"] == "TAKE_PROFIT_MARKET"]
                num_tps_restantes = len(tps)

                # Carrega o total de TPs esperados do active_trades.json
                original_expected_tps = state.get(symbol)
                
                if original_expected_tps is None:
                    # Se não está no JSON, o TradeExecutor ainda está abrindo as ordens ou é trade manual
                    continue

                # Se a corretora tem menos TPs do que o esperado no state,
                # significa que um ou mais TPs foram atingidos!
                if original_expected_tps > num_tps_restantes:
                    diff = original_expected_tps - num_tps_restantes
                    for _ in range(diff):
                        registrar_saida_trade('TP', symbol)
                    
                    # Atualiza o state e salva no arquivo
                    state[symbol] = num_tps_restantes
                    try:
                        with open(state_file, "w") as f:
                            json.dump(state, f)
                    except Exception as e:
                        logger.error(f"Erro ao salvar state atualizado no monitor: {e}")

                # Define o que deve ser ativado com base no número original de ordens abertas
                should_be = False
                should_ts = False

                if original_expected_tps == 4:
                    if num_tps_restantes == 3:                 # TP1 atingido
                        should_be = True
                    elif num_tps_restantes == 2:               # TP2 atingido
                        should_be = True
                    elif num_tps_restantes == 1:               # TP3 atingido
                        should_be = True
                    elif num_tps_restantes == 0:               # TP4 atingido → TS para os 10% restantes
                        should_ts = True
                elif original_expected_tps == 3:
                    if num_tps_restantes == 2:                 # TP1 atingido
                        should_be = True
                    elif num_tps_restantes == 1:               # TP2 atingido
                        should_be = True
                    elif num_tps_restantes == 0:               # TP3 atingido → TS para restante
                        should_ts = True
                elif original_expected_tps == 2:
                    if num_tps_restantes == 1:                 # TP1 atingido
                        should_be = True
                    elif num_tps_restantes == 0:               # TP2 atingido → TS para restante
                        should_ts = True

                # Anti-Race Condition Debounce: Confirma se o status se mantém após 5s
                if should_be or should_ts:
                    time.sleep(5)
                    ordens_res = broker.obter_ordens_abertas(symbol)
                    if not ordens_res or ordens_res.get("code") != 0:
                        continue
                    ordens = ordens_res.get("data", {}).get("orders", [])
                    tps = [o for o in ordens if o["type"] == "TAKE_PROFIT_MARKET"]
                    num_tps_confirmado = len(tps)
                    
                    if num_tps_confirmado != num_tps_restantes:
                        logger.info(f"⏳ - [Monitor] Falso positivo evitado para {symbol}. TPs mudaram de {num_tps_restantes} para {num_tps_confirmado}.")
                        continue

                # Busca ordens Stop Loss ou Trailing Stop
                sl_orders = [o for o in ordens if o["type"] == "STOP_MARKET"]
                ts_orders = [o for o in ordens if o["type"] in ["TRAILING_STOP_MARKET", "TRAILING_TP_SL"]]

                # Etapa 1: Break Even (não aplica se já tem Trailing Stop ativo)
                if should_be and len(ts_orders) == 0:
                    needs_be = False
                    if len(sl_orders) > 0:
                        current_sl_price = float(sl_orders[0].get("stopPrice", 0))
                        if abs(current_sl_price - avg_price) / avg_price > 0.001:
                            needs_be = True
                    else:
                        needs_be = True  # Sem SL → cria direto no Break Even

                    if needs_be:
                        logger.debug(f"🛡️ - [Monitor] Aplicando Break Even para {symbol} em {avg_price}...")
                        broker.cancela_ordem_sl(symbol)
                        time.sleep(0.5)
                        ret_sl = broker.enviar_ordem_sl(symbol, side_sl, quantidade, avg_price)
                        if ret_sl.get("code") == 0:
                            logger.debug(f"✅ - [Monitor] Break Even ativado para {symbol} em {avg_price}.")
                        else:
                            logger.error(f"❌ - [Monitor] Erro ao ativar Break Even: {ret_sl}")

                # Etapa 2: Trailing Stop (TP4 atingido — cobre os 10% finais sem TP fixo)
                elif should_ts:
                    if len(ts_orders) == 0:
                        logger.debug(f"🚀 - [Monitor] Ativando Trailing Stop para {symbol} (TP4 atingido, 10% restantes abertos)...")
                        broker.cancela_ordem_sl(symbol)
                        time.sleep(0.5)

                        callback_rate = float(os.getenv("TRAILING_STOP_RATE", "1.5"))
                        ret_ts = broker.enviar_trailing_stop(symbol, side_sl, quantidade, callback_rate=callback_rate)

                        if ret_ts.get("code") == 0:
                            logger.debug(f"✅ - [Monitor] Trailing Stop ativado para {symbol} a {callback_rate}%.")
                            # Marca o trailing stop como ativo
                            state[f"{symbol}_ts_active"] = True
                            try:
                                with open(state_file, "w") as f:
                                    json.dump(state, f)
                            except Exception as e:
                                logger.error(f"Erro ao salvar state com TS ativo no monitor: {e}")
                        else:
                            logger.error(f"❌ - [Monitor] Erro ao ativar Trailing Stop: {ret_ts}")

            time.sleep(15)

        except Exception as e:
            logger.error(f"❌ - Erro no loop do PositionMonitor: {e}")
            time.sleep(15)

if __name__ == "__main__":
    monitorar_posicoes()
