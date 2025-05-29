class MensagemTP:
    def __init__(self, symbol: str, tp_monitorado: str):
        self.symbol = symbol
        self.tp_monitorado = tp_monitorado

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "tp": self.tp_monitorado
        }
