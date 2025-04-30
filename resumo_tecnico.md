# 📊 Resumo Técnico - Projeto Telegram Trade Bot (Bybit Testnet)

Este projeto integra sinais de trade recebidos via Telegram com execução automática de ordens na corretora Bybit, utilizando a API v5 e operando inicialmente na **testnet**. 

## ✅ Funcionalidades Implementadas

### 1. Leitura de Sinais do Telegram
- Monitoramento de mensagens com sinais de trade (entrada, TPs e SL).
- Extração dos dados relevantes (par, tipo, entrada, TPs, stoploss).
- Armazenamento estruturado no banco e em JSON.

### 2. Controle de Configuração
- Arquivo `config.properties` centraliza todas as chaves da Bybit, BingX, e parâmetros de trade.
- Geração automática do arquivo `.env` com base nas escolhas feitas ao iniciar o bot.
- Suporte a testnet e mainnet.

### 3. Execução de Ordens na Bybit
- Consulta do saldo disponível em USDT.
- Cálculo da quantidade com base em `trade_percentage` configurado.
- Arredondamento com base no `qtyStep` recuperado dinamicamente da API `get_instruments_info`.
- Consulta ao preço de mercado via `get_tickers`.
- Criação de ordem de entrada `Market`.
- Criação de 4 TPs parciais via `set_trading_stop`, modo `Partial`, cada TP com `tpSize` calculado.
- Correção automática de envio de `tpLimitPrice`/`slLimitPrice` com base no tipo da ordem (`Market` ou `Limit`).

### 4. Logs e Erros
- Logs detalhados das chamadas à API.
- Tratamento de erros de envio de ordens e TP.

## 📌 Considerações Técnicas
- A API da Bybit requer que `tpLimitPrice` **não seja enviado** quando `tpOrderType="Market"`.
- Os parâmetros `qty`, `tpSize` e `slSize` devem respeitar `qtyStep` e `minNotionalValue`, consultados via `get_instruments_info`.

## 🛠 Próximos Passos
- Adicionar suporte à corretora BingX.
- Adicionar tratamento automático de monitoramentos para ajuste de SL ou fechamento parcial.
- Implementar painel web com Flask para visualizar ordens, TPs e desempenho da conta.
- Integração com sistema de relatórios mensais.

---

Gerado automaticamente em `bybit_trading_bot/resumo_tecnico.md`