from abc import ABC, abstractmethod

class BrokerInterface(ABC):
    @abstractmethod
    def enviar_ordem_tp_sl(self, symbol, side, leverage, side_leverage, tp, sl, quantidade, preco_mercado):
        pass

    @abstractmethod
    def ajustar_para_break_even(self, order_id, entry_price, tipo_ordem, par, quantidade):
        pass

    @abstractmethod
    def obter_saldo_disponivel(self):
        pass
    @abstractmethod
    def obter_preco_mercado(self, symbol):
        pass