class MensagemSinal:
    def __init__(
        self,
        symbol: str,
        tipo_ordem: str,
        stoploss: float,
        tp1: float,
        tp2: float,
        tp3: float,
        tp4: float,
        margem: str,
        alavancagem: str,
    ):
        self.symbol = symbol
        self.tipo_ordem = tipo_ordem
        self.stoploss = stoploss
        self.tp1 = tp1
        self.tp2 = tp2
        self.tp3 = tp3
        self.tp4 = tp4
        self.margem = margem
        self.alavancagem = alavancagem

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "tipo_ordem": self.tipo_ordem,
            "stoploss": self.stoploss,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "tp4": self.tp4,
            "margem": self.margem,
            "leverage": self.alavancagem,
        }
