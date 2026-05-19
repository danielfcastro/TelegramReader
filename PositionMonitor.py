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
            # A BingX swap v2 positions list retorna um array com todas as posições
            # Em modo One-Way, positionAmt indica a quantidade (positiva LONG, negativa SHORT)
            # Para economizar chamadas de API, pegamos a lista completa de posições
            # Nota: O BingXBroker atual não tem obter_todas_posicoes, então iteramos sobre as 
            # posições ativas se pudermos, ou podemos usar um endpoint de account.
            # Como o V2 /openApi/swap/v2/user/positions sem symbol retorna todas as posições:
            pos_res = broker._send_request("GET", "/openApi/swap/v2/user/positions", {})
            if not pos_res or pos_res.get("code") != 0:
                time.sleep(15)
                continue

            posicoes_ativas = [p for p in pos_res.get("data", []) if float(p["positionAmt"]) != 0]

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
                
                import json
                
                # Conta TPs
                tps = [o for o in ordens if o["type"] == "TAKE_PROFIT_MARKET"]
                num_tps_restantes = len(tps)

                # Carrega o total de TPs esperados do active_trades.json
                expected_tps = None
                state_file = "active_trades.json"
                if os.path.exists(state_file):
                    try:
                        with open(state_file, "r") as f:
                            state = json.load(f)
                        expected_tps = state.get(symbol)
                    except:
                        pass
                
                if expected_tps is None:
                    # Se não está no JSON, o TradeExecutor ainda está abrindo as ordens ou é trade manual
                    continue

                # Define o que deve ser ativado com base no número original de ordens abertas
                should_be = False
                should_ts = False
                
                if expected_tps == 4:
                    if num_tps_restantes == 2: should_be = True
                    if num_tps_restantes == 1: should_ts = True
                elif expected_tps == 3:
                    if num_tps_restantes == 1: should_be = True
                elif expected_tps <= 2:
                    pass # Trades muito parciais não aplicam BE complexo por segurança

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

                if should_be:
                    if len(ts_orders) > 0:
                        continue # Já tem trailing stop, ignora BE

                    needs_be = False
                    if len(sl_orders) > 0:
                        current_sl_price = float(sl_orders[0].get("stopPrice", 0))
                        if abs(current_sl_price - avg_price) / avg_price > 0.001:
                            needs_be = True
                    else:
                        needs_be = True # Se não tem SL, precisa criar no Break Even!
                        
                    if needs_be:
                        logger.info(f"🛡️ - [Monitor] Condição de Break Even detectada para {symbol}. Aplicando...")
                        broker.cancela_ordem_sl(symbol)
                        time.sleep(0.5)
                        ret_sl = broker.enviar_ordem_sl(symbol, side_sl, quantidade, avg_price)
                        if ret_sl.get("code") == 0:
                            logger.info(f"✅ - [Monitor] Break Even ativado com sucesso para {symbol} em {avg_price}.")
                        else:
                            logger.error(f"❌ - [Monitor] Erro ao ativar Break Even: {ret_sl}")
                
                elif should_ts:
                    if len(ts_orders) == 0:
                        logger.info(f"🚀 - [Monitor] Condição de Trailing Stop detectada para {symbol}. Aplicando...")
                        broker.cancela_ordem_sl(symbol)
                        time.sleep(0.5)
                        
                        callback_rate = float(os.getenv("TRAILING_STOP_RATE", "1.5"))
                        ret_ts = broker.enviar_trailing_stop(symbol, side_sl, quantidade, callback_rate=callback_rate)
                        
                        if ret_ts.get("code") == 0:
                            logger.info(f"✅ - [Monitor] Trailing Stop ativado com sucesso para {symbol} a {callback_rate}%.")
                        else:
                            logger.error(f"❌ - [Monitor] Erro ao ativar Trailing Stop: {ret_ts}")

            time.sleep(15)

        except Exception as e:
            logger.error(f"❌ - Erro no loop do PositionMonitor: {e}")
            time.sleep(15)

if __name__ == "__main__":
    monitorar_posicoes()
