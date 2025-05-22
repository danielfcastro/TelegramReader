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
    """
    Endpoint para receber sinais do TelegramReader e executar ordens na corretora.

    - Normaliza os dados recebidos.
    - Valida a existência do sinal no banco.
    - Calcula a quantidade com base no saldo disponível.
    - Envia a ordem com SL e configura múltiplos TPs.
    - Atualiza o banco com os dados da execução.

    Args:
        request (Request): Objeto da requisição contendo JSON com 'id' e 'pair'.

    Returns:
        JSONResponse: {'status': 'ok'} ou {'erro': '...'}
    """

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
            _id = sinal['id']
            symbol = sinais[0]["par"].replace("/", "-").upper()
            try:
                preco_mercado = broker.obter_preco_mercado(symbol)
            except Exception as e:
                logger.error(f"❌ - Erro ao obter preço de mercado de {symbol} - Exception: {e}")
                database.db.ordem_desabilitar(_id)
                continue
            saldo = broker.obter_saldo_disponivel()
            tipo_ordem = str(sinal["tipo_ordem"]).upper()
            trade_percentage = float(os.getenv("TRADE_PERCENTAGE", "3"))
            valor_trade = saldo * (trade_percentage / 100)
            quantidade = ajustar_quantidade( valor_trade  / preco_mercado, step=0.0001)
            symbol = sinal["par"].replace("/", "-")
            logger.debug(f"⚠️ - symbol: {symbol} - saldo: {saldo} - trade_percentage: {trade_percentage} - quantidade: {quantidade} - preco_mercado: {preco_mercado} - valor_trade: {valor_trade} - tipo_ordem: {tipo_ordem}")
            try:
                sucesso, entry_price_retorno, order_id, quantidade = broker.enviar_ordem_tp_sl(
                    symbol=symbol,
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
                    database.db.atualizar_status_tp(par=symbol, numero_tp=1, novo_status=2)
                    database.db.atualizar_status_tp(par=symbol, numero_tp=2, novo_status=2)
                    database.db.atualizar_status_tp(par=symbol, numero_tp=3, novo_status=2)
                    database.db.atualizar_status_tp(par=symbol, numero_tp=4, novo_status=2)
                    logger.info(f"⚠️ - Ordem enviada com sucesso para symbol: ID: {_id} - symbol: {symbol} - saldo: {saldo} - trade_percentage: {trade_percentage} - quantidade: {quantidade} - preco_mercado: {preco_mercado} - valor_trade: {valor_trade} - tipo_ordem: {tipo_ordem} - order_id: {order_id} - quantidade: {quantidade}")

                    # Recuperar TPs do banco para atualizar com a quantidade real
                    tps = database.db.take_profits_por_sinal(sinal_id=_id)
                    for tp in tps:
                        tp_quant = round(quantidade * tp["proporcao"], 6)
                        database.db.ordem_atualizar_tp(
                            sinal_id=_id,
                            numero=tp["numero"],
                            quantidade=tp_quant,
                            valor=tp["valor"]
                        )
                        broker.ajustar_take_profit(
                            symbol=symbol,
                            position_side=tipo_ordem,
                            quantity=tp_quant,
                            stop_price=tp["valor"],
                            numero=tp["numero"],
                            order_id=order_id
                        )

                else:
                    database.db.ordem_desabilitar(_id)
                    logger.warning(f"⚠️ - Falha ao enviar ordem para {symbol} - ID: {_id}")
            except Exception as e:
                logger.exception(f"❌ - Erro inesperado ao enviar ordem para {symbol}: {e}")

    return {"status": "ok"}



@app.post("/monitoramento")
async def receber_sinal_monitoramento(request: Request):
    """
    Endpoint para processar um sinal de monitoramento (TP atingido).

    - Marca o TP como ATINGIDO no banco (status 3).
    - Cancela SL anterior.
    - Se for TP2, TP3 ou TP4, move o SL para Break Even.
    - Tenta até 3 vezes configurar o novo SL na corretora.

    Args:
        request (Request): JSON contendo 'pair' e 'target_monitorado' (TP1–TP4).

    Returns:
        JSONResponse: {'status': 'ok'}, 'failed', 'no_active_orders' ou 'no_order'
    """

    dados = await request.json()
    logger.info(f"🔍 - POST /monitoramento recebido: {dados}")

    par = dados["pair"]
    tp_monitorado = int(dados.get("target_monitorado", 1))
    symbol = par.replace("/", "-")

    # Atualiza TP para status ATINGIDO (3)
    logger.debug(f"✅ - par: {par} - tp_monitorado: {tp_monitorado}")
    database.db.atualizar_status_tp(par, tp_monitorado, novo_status=3)

    # Soma quantidades dos TPs com status = 2 (CONFIGURADO)
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
    """
    Inicializa o servidor FastAPI com o Uvicorn em localhost:8000.
    """

    # Inicia o servidor REST
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    iniciar_executor()