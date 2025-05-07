from abc import ABC, abstractmethod

class BrokerInterface(ABC):
    @abstractmethod
    def enviar_ordem_tp_sl(self, symbol, side, leverage, side_leverage, tp, sl, quantidade, preco_mercado):
        pass

    @abstractmethod
    def cancela_stop_loss(self, symbol):
        pass

    @abstractmethod
    def ajustar_para_break_even(self, symbol, position_side, quantity, stop_price, order_id):
        pass

    @abstractmethod
    def obter_saldo_disponivel(self):
        pass

    @abstractmethod
    def obter_preco_mercado(self, symbol):
        pass

    @abstractmethod
    def ativar_trailing_stop(self, symbol, order_id, side, quantity, price_rate, position_side):
        pass

    @abstractmethod
    def get_open_order_info(self, symbol, order_id):
        pass
