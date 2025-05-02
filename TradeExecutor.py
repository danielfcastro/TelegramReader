import time
from database.db import (
    buscar_sinal_execucao,
    buscar_sinal_para_be,
    marcar_be_executado,
    marcar_ordem_enviada,
    incrementar_retry_be,
    incrementar_retry_order    
)

def iniciar_executor(broker):
    print("✅ Executor iniciado com 1 thread para trade + break even")

    while True:
        try:
            sinal = buscar_sinal_execucao()
            if sinal:
                print(f"📦 Enviando ordem para {sinal['par']}")
                sucesso, entry_price, order_id = broker.enviar_ordem_tp_sl(sinal)
                if sucesso:
                    marcar_ordem_enviada(sinal["id"], entry_price, order_id)
                else:
                    incrementar_retry_order(sinal["id"])
            else:
                # Nenhuma ordem nova, vamos verificar BE
                sinal_be = buscar_sinal_para_be()
                if sinal_be:
                    print(f"⚙️ Ajustando BE para {sinal_be['par']}")
                    sucesso = broker.ajustar_para_break_even(
                        id=sinal_be["id"],
                        order_id=sinal_be["order_id"],
                        entry_price=sinal_be["entry_price"],
                        tipo_ordem=sinal_be["tipo_ordem"],
                        par=sinal_be["par"]
                    )
                    if sucesso:
                        marcar_be_executado(sinal_be["id"], sinal_be["entry_price"])
                    else:
                        incrementar_retry_be(sinal_be["id"])
            time.sleep(5)

        except KeyboardInterrupt:
            print("\n🛑 Executor encerrado pelo usuário.")
            break
        except Exception as e:
            print(f"❌ Erro geral no executor: {e}")


