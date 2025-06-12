class MensagemTP:
    def __init__(self, symbol: str, tp: str, order_id: int = None):
        self.symbol = symbol
        self.tp = tp
        self.order_id = order_id

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "tp": self.tp,
            "order_id": self.order_id
        }

    def __repr__(self):
        return f"MensagemTP(symbol={self.symbol}, TP={self.tp}, order_id={self.order_id})"