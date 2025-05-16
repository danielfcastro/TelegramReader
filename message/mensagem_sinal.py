from typing import Optional


class MensagemSinal:
    def __init__(
        self,
        pair: str,
        tipo_ordem: Optional[str] = None,
        stoploss: Optional[float] = None,
        tp1: Optional[float] = None,
        tp2: Optional[float] = None,
        tp3: Optional[float] = None,
        tp4: Optional[float] = None,
        margem: Optional[str] = None,
        alavancagem: Optional[str] = None,
        tp_monitorado: Optional[str] = None,
    ):
        self.pair = pair
        self.tipo_ordem = tipo_ordem
        self.stoploss = stoploss
        self.tp1 = tp1
        self.tp2 = tp2
        self.tp3 = tp3
        self.tp4 = tp4
        self.margem = margem
        self.alavancagem = alavancagem
        self.tp_monitorado = tp_monitorado

    def is_trade(self):
        return self.tipo_ordem is not None and self.stoploss is not None

    def is_monitoramento(self):
        return self.tp_monitorado is not None

    def to_dict(self):
        return {
            "pair": self.pair,
            "type": self.tipo_ordem,
            "stoploss": self.stoploss,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "tp4": self.tp4,
            "margin": self.margem,
            "leverage": self.alavancagem,
            "tp": self.tp_monitorado,
        }
