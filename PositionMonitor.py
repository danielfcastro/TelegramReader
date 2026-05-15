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
                position_side = "LONG" if float(pos["positionAmt"]) > 0 else "SHORT"
                side_sl = "SELL" if position_side == "LONG" else "BUY"

                # Obtém todas as ordens abertas para o símbolo
                ordens_res = broker.obter_ordens_abertas(symbol)
                if not ordens_res or ordens_res.get("code") != 0:
                    continue
                
                ordens = ordens_res.get("data", {}).get("orders", [])
                
                # Conta TPs
                tps = [o for o in ordens if o["type"] == "TAKE_PROFIT_MARKET"]
                num_tps_restantes = len(tps)

                # Busca ordens Stop Loss ou Trailing Stop
                sl_orders = [o for o in ordens if o["type"] == "STOP_MARKET"]
                ts_orders = [o for o in ordens if o["type"] in ["TRAILING_STOP_MARKET", "TRAILING_TP_SL"]]

                if num_tps_restantes == 2:
                    # TP2 atingido, requer Break Even
                    if len(ts_orders) > 0:
                        continue # Já tem trailing stop, ignora BE

                    if len(sl_orders) > 0:
                        # Pega o preço da ordem SL atual
                        current_sl_price = float(sl_orders[0].get("stopPrice", 0))
                        # Se o SL ainda não for igual ao entry price (avg_price), aplica BE
                        if abs(current_sl_price - avg_price) / avg_price > 0.001:  # Tolerância de 0.1%
                            logger.info(f"🛡️ - [Monitor] TP2 detectado para {symbol}. Aplicando Break Even...")
                            broker.cancela_ordem_sl(symbol)
                            time.sleep(0.5)
                            ret_sl = broker.enviar_ordem_sl(symbol, side_sl, quantidade, avg_price)
                            if ret_sl.get("code") == 0:
                                logger.info(f"✅ - [Monitor] Break Even ativado com sucesso para {symbol} em {avg_price}.")
                            else:
                                logger.error(f"❌ - [Monitor] Erro ao ativar Break Even: {ret_sl}")
                
                elif num_tps_restantes == 1:
                    # TP3 atingido, requer Trailing Stop
                    if len(ts_orders) == 0:
                        logger.info(f"🚀 - [Monitor] TP3 detectado para {symbol}. Aplicando Trailing Stop...")
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
