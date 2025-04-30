# 📄 README.md — Projeto Telegram Crypto Signal Bot

## 📚 Descrição

Este projeto é dividido em **dois serviços independentes**:

- **TelegramSignalReader**: Monitora mensagens de sinais de trading em grupos ou canais do Telegram e grava em um banco de dados.
- **TradeExecutor**: Monitora o banco de dados, identifica sinais pendentes e envia ordens automáticas para a ByBIT Testnet.

✅ Arquitetura desacoplada, modular e escalável.  
✅ Configuração fácil para ambiente de testes e produção.  
✅ Pronto para migrar de SQLite para PostgreSQL.

---

## 🛠️ Estrutura do Projeto

```
ProjetoTelegramTradeBot/
├── database/
│   ├── criar_tabela.py
│   ├── sinais.db
│   ├── upgrade_database.py
├── example/
│   ├── exemplo_sinal.json
├── integration/
│   ├── bingx_trading.py
│   ├── bybit_trading.py
├── logs/
├── venv/
├── web_dashboard/
│   ├── templates/
│   │   ├── apdashboardp.html
│   ├── app.py
├── .env
├── .gitignore
├── config.properties
├── docker-compose.yml
├── extrator_sinal.py
├── ler_json.py
├── ler_sinais.py
├── minha_sessao.session
├── README.md
├── requirements.txt
├── start_all.py
├── TelegramReader.py
├── TradeExecutor.py
└── utils.py

```

---

## 📦 Instalação

1. Clone ou copie este projeto para sua máquina.

2. Crie o ambiente virtual Python:

```bash
python -m venv venv
```

3. Ative o ambiente virtual:

- **Windows**:

```bash
venv\Scripts\activate
```

- **Linux/macOS**:

```bash
source venv/bin/activate
```

4. Instale as dependências:

```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuração

Edite o arquivo `config.properties`:

```ini
# Telegram Config
api_id=SEU_API_ID_DO_TELEGRAM
api_hash=SEU_API_HASH_DO_TELEGRAM
grupo_id=ID_DO_GRUPO_OU_CANAL

# ByBIT Testnet Config
bybit_api_key=SUA_API_KEY
bybit_api_secret=SEU_API_SECRET

# Trading Strategy
trade_percentage=3  # Percentual do saldo disponível para usar em cada trade

# Database Config (modo atual: SQLite)
database_mode=sqlite
sqlite_db_path=database/sinais.db

# Futuro (PostgreSQL)
# database_mode=postgresql
# postgres_host=localhost
# postgres_port=5432
# postgres_user=usuario
# postgres_password=senha
# postgres_db=sinais
```

---

## 🏁 Primeiro Uso

1. Crie o banco de dados:

```bash
python database/criar_tabela.py
```

2. Inicie o sistema (duas formas):

### Forma 1: Script start_all.py

```bash
python start_all.py
```

### Forma 2: Clique duplo no `start_bot.bat` (Windows)

> Crie um arquivo `start_bot.bat` com o seguinte conteúdo:

```bat
@echo off
cd /d %~dp0
python start_all.py
pause
```

---

## 📦 Rodar com Docker

Se preferir rodar tudo isolado em containers:

1. Crie um `docker-compose.yml` com o seguinte conteúdo:

```yaml
version: '3'
services:
  telegram_bot:
    build: .
    container_name: telegram_signal_reader
    command: python TelegramSignalReader.py
    volumes:
      - .:/app
    restart: unless-stopped

  trade_executor:
    build: .
    container_name: trade_executor
    command: python TradeExecutor.py
    volumes:
      - .:/app
    restart: unless-stopped
```

2. Rode:

```bash
docker-compose up -d
```

---

## 📋 Logs

- Mensagens capturadas: `logs/telegram_reader.log`
- Ordens enviadas: `logs/trade_executor.log`

---

## 🧠 Observações

- Este projeto usa **ByBIT Testnet** — perfeito para treinar sem risco financeiro.
- Posteriormente, será possível migrar para **produção real** na ByBIT com poucas alterações no endpoint e nas chaves.
- O projeto já está preparado para usar **PostgreSQL** no lugar do SQLite quando for necessário escalar.

---

## 📈 Melhorias Futuras

- Adicionar suporte a stop móvel (trailing stop).
- Implementar múltiplos targets automáticos.
- Conectar a APIs de corretoras alternativas (Binance, OKX, KuCoin).
- Interface web para monitorar sinais em tempo real.

---

# 🚀 Bora automatizar!
---

## 🌐 Rodar o Painel Web

O Painel Web permite visualizar em tempo real:

- Sinais captados
- Status de execução
- Ordens pendentes ou executadas

### Como rodar o painel:

1. Instale o Flask, se ainda não tiver:

```bash
pip install flask
```

2. Vá até a pasta do painel:

```bash
cd web_dashboard
```

3. Inicie o servidor:

```bash
python app.py
```

4. Acesse no navegador:

> http://localhost:5000/

O painel mostrará os sinais captados e seu status!

---

TODO

To use Demo Trading API, you need to:
1) switch over to Demo on Mainnet (bybit.com)
2) head over to https://www.bybit.com/app/user/api-management
3) create an API key while in Demo Trading mode

You can now use this API for Demo Trading. Assuming you use pybit, it's done by setting testnet=False and demo=True

5. Resumo Técnico
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
=======