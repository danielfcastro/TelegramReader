class MensagemTP:
    def __init__(self, symbol: str, tp: str):
        self.symbol = symbol
        self.tp = tp
        self.order_id = None

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "tp": self.tp,
            "order_id": self.order_id
        }
