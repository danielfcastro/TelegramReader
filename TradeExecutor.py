# Novo TradeExecutor.py com API REST
import asyncio
import os

import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

import database.db
from integration.BingXBroker import BingXBroker
from utils import logger, ajustar_quantidade

app = FastAPI()

broker = BingXBroker()

# Nova rota para receber sinais do TelegramReader
@app.post("/sinal")
async def receber_sinal_ordem(request: Request):
    dados = await request.json()
    logger.info(f"📥 - POST /sinal recebido Request - {dados}")

    # Normaliza nomes de chave para manter compatibilidade
    dados["par"] = dados.pop("pair", None)

    # Evite acesso direto sem verificação
    if not dados.get("par") or not dados.get("id"):
        logger.error("❌ - Campos obrigatórios ausentes em dados recebidos.")
        return JSONResponse(content={"erro": "Campos obrigatórios ausentes"}, status_code=400)

    sinais = database.db.sinal_disparar_trade()
    for sinal in sinais:
        if sinal['par'] == dados['par'] and sinal['id'] == dados['id']:
            symbol = sinais[0]["par"].replace("/", "-").upper()
            try:
                preco_mercado = broker.obter_preco_mercado(symbol)
            except Exception as e:
                logger.error(f"❌ - Erro ao obter preço de mercado de {symbol} - Exception: {e}")
                continue
            saldo = broker.obter_saldo_disponivel()
            tipo_ordem = str(sinal["tipo_ordem"]).upper()
            trade_percentage = float(os.getenv("TRADE_PERCENTAGE", "3"))
            valor_trade = saldo * (trade_percentage / 100)
            quantidade = ajustar_quantidade( valor_trade  / preco_mercado, step=0.0001)
            logger.debug(f"⚠️ - symbol: {symbol} - saldo: {saldo} - quantidade: {quantidade} - preco_mercado: {preco_mercado} - valor_trade: {valor_trade} - tipo_ordem: {tipo_ordem}")
            try:
                sucesso, preco_mercado, order_id, quantidade = broker.enviar_ordem_tp_sl(
                    symbol=sinal["par"].replace("/", "-"),
                    side = tipo_ordem,
                    leverage=sinal["alavancagem"],
                    side_leverage=sinal["margem"],
                    tp=None,  # agora os TPs vêm da tabela
                    sl=sinal["sl"],
                    quantidade=quantidade,
                    preco_mercado=None,
                    id_sinal=sinal["id"]
                )

                if sucesso:
                    database.db.ordem_enviada(id_sinal=sinal["id"],
                                              entry_price=preco_mercado,
                                              order_id=order_id, quantidade=quantidade)
                    logger.info(f"✅ - Ordem enviada com sucesso para {sinal['par']} - ID: {sinal['id']}")

                    # Recuperar TPs do banco para atualizar com a quantidade real
                    tps = database.db.take_profits_por_sinal(sinal_id=sinal["id"])
                    for tp in tps:
                        tp_quant = round(quantidade * tp["proporcao"], 6)
                        database.db.ordem_atualizar_tp(
                            sinal_id=sinal["id"],
                            numero=tp["numero"],
                            quantidade=tp_quant,
                            valor=tp["valor"]
                        )
                        broker.ajustar_take_profit(
                            symbol=sinal["par"].replace("/", "-"),
                            position_side=sinal["tipo_ordem"],
                            quantity=tp_quant,
                            stop_price=tp["valor"],
                            numero=tp["numero"],
                            order_id=order_id
                        )

                else:
                    database.db.ordem_desabilitar(sinal["id"])
                    logger.warning(f"⚠️ - Falha ao enviar ordem para {sinal['par']} - ID: {sinal['id']}")
            except Exception as e:
                logger.exception(f"❌ - Erro inesperado ao enviar ordem para {sinal['par']}: {e}")

    return {"status": "ok"}



@app.post("/monitoramento")
async def receber_sinal_monitoramento(request: Request):
    dados = await request.json()
    logger.info(f"🔍 - POST /monitoramento recebido: {dados}")

    par = dados["pair"]
    tp_monitorado = int(dados.get("target_monitorado", 1))
    symbol = par.replace("/", "-")

    # Atualiza TP para status ATINGIDO (3)
    logger.debug(f"✅ - par: {par} - tp_monitorado: {tp_monitorado}")
    database.db.atualizar_status_tp(par, tp_monitorado, novo_status=3)

    # Soma quantidades dos TPs com status = 2 (AGUARDANDO ENVIO DE SL)
    quantidade = database.db.somar_quantidades_tps_ativos(par)

    if not quantidade or quantidade == 0:
        logger.warning(f"⚠️ - Nenhuma quantidade ativa encontrada para {par} no TP{tp_monitorado}")
        return {"status": "no_active_orders"}

    # Cancelar qualquer SL anterior
    broker.cancela_stop_loss(par)

    # Buscar informações da ordem principal
    ordem = database.db.ordem_info(dados["pair"], exigir_break_even_inativo=False)
    if not ordem:
        logger.warning(f"⚠️ - Nenhuma ordem encontrada para {par}")
        return {"status": "no_order"}

    # Decide o novo stop_price com base no TP monitorado
    stop_price = ordem["sl"] if tp_monitorado == 1 else ordem["entry_price"]

    # Se TP2, TP3 ou TP4: atualiza sl da ordem no banco
    if tp_monitorado != 1:
        database.db.atualizar_stop_loss(par, novo_sl=ordem["entry_price"])

    # Tentar até 3 vezes ajustar o SL
    for tentativa in range(3):
        sucesso = broker.ajustar_stop_loss(
            symbol=symbol,
            position_side="BOTH",
            quantity=quantidade,
            stop_price=stop_price,
            order_id=ordem["order_id"]
        )
        if sucesso:
            logger.info(f"✅ - SL ajustado para {par} - ordem {ordem['order_id']}")
            return {"status": "ok"}

        logger.warning(f"⚠️ - Tentativa {tentativa + 1}/3 falhou ao ajustar SL para {par}")
        await asyncio.sleep(1.5)

    logger.error(f"❌ - Falha ao ajustar SL após 3 tentativas para {par}")
    return {"status": "failed"}



# Inicializa a thread do executor e o servidor REST

def iniciar_executor():
    # Inicia o servidor REST
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    iniciar_executor()