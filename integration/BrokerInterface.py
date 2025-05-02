from abc import ABC, abstractmethod

class BrokerInterface(ABC):
    @abstractmethod
    def enviar_ordem_tp_sl(self, sinal):
        pass

    @abstractmethod
    def ajustar_para_break_even(self, par):
        pass