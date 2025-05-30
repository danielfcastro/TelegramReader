class MensagemTP:
    def __init__(self, symbol: str, tp_monitorado: str):
        self.symbol = symbol
        self.tp_monitorado = tp_monitorado
        self.order_id = None

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "tp": self.tp_monitorado
            "order_id": self.order_id
        }
