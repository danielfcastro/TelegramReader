import unittest

from message.mensagem_sinal import MensagemSinal
from message.mensagem_tp import MensagemTP
from utils import classificar_mensagem

class TestClassificarMensagem(unittest.TestCase):

    def test_mensagem_sinal_valida(self):
        mensagem = {
            "symbol": "BTC-USDT",
            "tipo_ordem": "LONG",
            "stoploss": 25800.5,
            "tp1": 26200.0,
            "tp2": 26400.0,
            "tp3": 26600.0,
            "tp4": 27000.0,
            "leverage": "20X",
            "margem": "Cross"
        }
        tipo, dados = classificar_mensagem(mensagem)
        self.assertEqual(tipo, "sinal")
        self.assertIsInstance(dados, MensagemSinal)

    def test_mensagem_tp_valida(self):
        mensagem = {
            "symbol": "BTC-USDT",
            "tp": "TP2"
        }
        tipo, dados = classificar_mensagem(mensagem)
        self.assertEqual(tipo, "monitoramento")
        self.assertIsInstance(dados, MensagemTP)

    def test_mensagem_invalida_campos_faltando(self):
        mensagem = {
            "symbol": "BTC-USDT"
        }
        tipo, dados = classificar_mensagem(mensagem)
        self.assertIsNone(tipo)
        self.assertIsNone(dados)

    def test_mensagem_vazia(self):
        mensagem = {}
        tipo, dados = classificar_mensagem(mensagem)
        self.assertIsNone(tipo)
        self.assertIsNone(dados)


if __name__ == '__main__':
    unittest.main()
