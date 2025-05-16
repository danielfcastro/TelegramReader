from abc import ABC, abstractmethod

class BrokerInterface(ABC):
    @abstractmethod
    def enviar_ordem_tp_sl(self, symbol, side, leverage, side_leverage, tp, sl, quantidade, preco_mercado, id_sinal):
        pass

    @abstractmethod
    def cancela_stop_loss(self, symbol):
        pass

    @abstractmethod
    def ajustar_stop_loss(self, symbol, position_side, quantity, stop_price, order_id):
        pass

    @abstractmethod
    def ajustar_take_profit(self, symbol, position_side, quantity, stop_price, numero):
        pass

    @abstractmethod
    def obter_saldo_disponivel(self):
        pass

    @abstractmethod
    def obter_preco_mercado(self, symbol):
        pass

    @abstractmethod
    def get_open_order_info(self, symbol, order_id):
        pass

    @abstractmethod
    def send_order_with_constraints_adjusted(self, symbol, side, leverage, side_leverage,tp, sl, preco_mercado, limite_usdt, id_sinal):
        pass
