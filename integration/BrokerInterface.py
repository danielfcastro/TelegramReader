from abc import ABC, abstractmethod

from message.mensagem_sinal import MensagemSinal


class BrokerInterface(ABC):
    @abstractmethod
    def enviar_ordem_tp_sl(self, mensagem: MensagemSinal, quantidade):
        pass

    @abstractmethod
    def cancela_stop_loss(self, symbol):
        pass

    @abstractmethod
    def ajustar_stop_loss(self, symbol, position_side, quantity, stop_price, order_id, current_order_side):
        pass

    @abstractmethod

    def ajustar_take_profit(self, symbol, position_side, quantity, stop_price, order_id, numero):
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
    def cancela_order(self, symbol, order_id=None):
        pass

    @abstractmethod
    def obter_todas_ordens_abertas(self, symbol):
        pass

    @abstractmethod
    def verificar_tipo_margem(self, symbol):
        pass

    @abstractmethod
    def mudar_tipo_margem(self, symbol):
        pass

    @abstractmethod
    def fecha_ordem_mercado(self, symbol):
        pass

    @abstractmethod
    def cancela_ordem_tp(self, symbol):
        pass

    @abstractmethod
    def cancela_ordem_sl(self, symbol):
        pass