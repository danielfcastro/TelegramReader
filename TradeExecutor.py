import time
from types import NoneType
from database.db import (
    buscar_sinal_execucao,
    buscar_sinal_para_be,
    marcar_ordem_para_be_executado,
    marcar_ordem_enviada,
    incrementar_retry_be,
    incrementar_retry_order,
)
#from bingx.api import BingxAPI
#API_KEY ='bmIBQcCg2jzDwqRBoG6IBRo8KGIEJNcM0VjOMBI1yJxKgFMhg7nDQKs9bxsLBE355lS25Kgpwb3KPX1SnPdgQ'
#SECRET_KEY='LsXlN8NeXdzmV2IkpCYDwrpRPzygRElUtthuKoQzGgszNsx2zFdYkfxERMnS9yeSGW55saxXsBF9fBg'

debug = False
#bingx = BingxAPI(API_KEY, SECRET_KEY, timestamp="local")

def iniciar_executor(broker):
    #print(bingx.get_perpetual_balance())
    print("✅ Executor iniciado com 1 thread para trade + break even")

    while True:
        try:
            #total = conta_sinais_execucao()
            #print(f"Total de sinais pendentes: {total}")
            #if total == 0:
            #    time.sleep(3)
            #    continue
            sinais = buscar_sinal_execucao()
            time.sleep(5)
            if debug: 
                print(f">>> tipo de sinais: {type(sinais)} | valor: {sinais!r}")
                if sinais is None:
                    print("✅ É None mesmo")
                else:
                    print("🚫 NÃO é None")
            if not isinstance(sinais, NoneType):
                for sinal in sinais:
                    print(f"📦 Enviando ordem para {sinal['par']}")
                    sucesso, entry_price, order_id = broker.enviar_ordem_tp_sl(sinal)
                    if sucesso:
                        marcar_ordem_enviada(sinal["id"], entry_price, order_id)
                    else:
                        incrementar_retry_order(sinal["id"])
            else:
                # Nenhuma ordem nova, vamos verificar BE
                sinal_be = buscar_sinal_para_be()
                for info in sinal_be:
                    if info:
                        print(f"⚙️ Ajustando BE para {info['par']}")
                        sucesso = broker.ajustar_para_break_even(
                            id=info["id"],
                            order_id=info["order_id"],
                            entry_price=info["entry_price"],
                            tipo_ordem=info["tipo_ordem"],
                            par=info["par"]
                        )
                        if sucesso:
                            marcar_ordem_para_be_executado(info["par"])
                        else:
                            incrementar_retry_be(info["id"])
            time.sleep(5)

        except KeyboardInterrupt:
            print("\n🛑 Executor encerrado pelo usuário.")
            break
        except Exception as e:
            print(f"❌ Erro geral no executor: {e}")