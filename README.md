# 📡 TelegramReader — Bot de Trading Automatizado / Automated Trading Bot

[Português 🇧🇷](#português) | [English 🇬🇧](#english-uk)

---

# Português

Bot que lê sinais de trading de um grupo privado do Telegram e os executa automaticamente na corretora **BingX Futures**, com gestão de risco progressiva via Break Even e Trailing Stop.

---

## 🗺️ Visão Geral da Arquitetura

O sistema é composto por **3 serviços independentes** que rodam em paralelo, gerenciados pelo `start_all.py` (ou via `systemd`):

```
┌─────────────────────────────────────────────────────────────┐
│                        Telegram Group                       │
│          (Sinais de entrada + Atualizações de TP)           │
└───────────────────────────┬─────────────────────────────────┘
                            │ Mensagem recebida
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    TelegramReader.py                        │
│  • Escuta mensagens com Telethon                            │
│  • Classifica: SINAL (trade novo) ou MONITORAMENTO (TP hit) │
│  • POST /trade  →  TradeExecutor                            │
│  • PUT  /tp     →  TradeExecutor                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP (localhost)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    TradeExecutor.py                         │
│  Flask API porta 8001                                       │
│  POST /trade → Abre 5 ordens na BingX                       │
│  PUT  /tp    → Ajusta SL (BE) ou ativa Trailing Stop        │
└───────────────────────────┬─────────────────────────────────┘
                            │ API BingX
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   PositionMonitor.py                        │
│  • Daemon de polling (a cada 15s)                           │
│  • Fallback independente do Telegram                        │
│  • Detecta TPs executados via contagem de ordens abertas    │
│  • Aplica Break Even e Trailing Stop automaticamente        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Estratégia de Execução — 5 Ordens por Sinal

Cada sinal recebido abre **5 ordens de mercado simultâneas** com proporções específicas do capital alocado:

| Ordem | Volume | TP Fixo   | SL | Ação ao ser atingida |
|-------|--------|-----------|----|----------------------|
| #1    | 10%    | TP1       | ✅ | Move SL → Break Even |
| #2    | 20%    | TP2       | ✅ | Move SL → Break Even (se não estiver) |
| #3    | 50%    | TP3       | ✅ | Move SL → Break Even (se não estiver) |
| #4    | 10%    | TP4       | ✅ | Ativa Trailing Stop para os 10% restantes |
| #5    | 10%    | ❌ Nenhum | ✅ | Rastreada **apenas** pelo Trailing Stop |

> **Os 10% da Ordem #5 ficam abertos sem TP fixo**, aguardando o Trailing Stop que é ativado quando a Ordem #4 (TP4) é atingida. Isso permite capturar movimentos adicionais além do TP4 sem limitar o upside.

---

## 🛡️ Gestão de Risco Progressiva

### Sequência de eventos após abertura de posição

```
Entrada
  │
  ├─ TP1 atingido (10% fechado)
  │     └─► SL de todas as ordens → BREAK EVEN (preço de entrada)
  │          ✅ A partir daqui, pior caso = operação zerada
  │
  ├─ TP2 atingido (20% fechado)
  │     └─► Confirma SL no Break Even (se por algum motivo não estiver)
  │
  ├─ TP3 atingido (50% fechado)
  │     └─► Confirma SL no Break Even (se por algum motivo não estiver)
  │
  ├─ TP4 atingido (10% fechado)
  │     └─► TRAILING STOP ativado sobre os 10% restantes (Ordem #5)
  │          • Segue o preço com callback configurável (padrão: 1.5%)
  │          • Captura movimento adicional sem TP fixo
  │
  └─ Trailing Stop disparado
        └─► Posição #5 encerrada automaticamente pela corretora
```

### Anti-Race Condition (PositionMonitor)
O `PositionMonitor` implementa um **debounce de 5 segundos**: antes de agir, consulta novamente a API para confirmar que o número de TPs realmente mudou. Isso evita ações errôneas causadas por delays na API ou ordens em execução simultânea.

### Detecção de Estado (Stateless)
O sistema é **stateless** — não usa banco de dados. A lógica de monitoramento funciona assim:

- O `TradeExecutor` salva no `active_trades.json` **quantos TPs com preço fixo** foram abertos (ex: `"VELVET-USDT": 4`)
- O `PositionMonitor` consulta a API e conta os `TAKE_PROFIT_MARKET` (TPs com preço fixo) ainda abertos
- A diferença entre o esperado e o atual revela qual TP foi atingido, acionando as proteções e o Trailing Stop para a 5ª ordem (que não possui TP fixo)

| TPs Fixo Abertos Restantes       | Situação detectada | Ação Aplicada |
|----------------------------------|--------------------|---------------|
| `expected - 1`                   | TP1 atingido       | Move Stop Loss para Break Even |
| `expected - 2`                   | TP2 atingido       | Garante Stop Loss no Break Even |
| `expected - 3`                   | TP3 atingido       | Garante Stop Loss no Break Even |
| `0` (Todos TPs fixos executados) | TP4 atingido       | Cancela SL e ativa Trailing Stop na 5ª ordem (restante de 10%) |

> 💡 **Nota sobre as 5 Ordens:** Das 5 ordens abertas para cada sinal, apenas as 4 primeiras possuem Take Profits de preço fixo (TP1, TP2, TP3 e TP4). A 5ª ordem é aberta sem TP fixo e é gerida exclusivamente pelo Trailing Stop, que passa a monitorá-la assim que a 4ª ordem (TP4) é liquidada.

---

## 📊 Trade Outcome Analytics

O bot possui um sistema de telemetria de performance persistente e em tempo real, consolidando métricas no arquivo `trade_analytics.json`.

### Métricas e Classificação

Os trades são classificados em três tipos de desfechos distintos:

* **A (`tp_hits`):** Incrementado a cada Take Profit fixo (TP1–TP4) executado com sucesso.
* **B (`sl_hits`):** Incrementado quando a posição é encerrada pelo Stop Loss original ou no Break Even.
* **C (`trailing_hits`):** Incrementado quando os 10% finais (Ordem #5) são fechados pelo Trailing Stop.

### Taxa de Sucesso

```
Success Rate = (A + C) / (A + B + C) × 100
```

### Funcionamento
- **Persistência:** Métricas salvas em `trade_analytics.json` — sobrevivem a restarts.
- **Detecção de Saída:** O `PositionMonitor` compara posições ativas na corretora com `active_trades.json` e identifica o tipo de saída via flag `_ts_active`.
- **Relatório Final (`atexit`):** Ao encerrar o `TradeExecutor`, um resumo consolidado é gravado no `app.log`.

Exemplo de log em tempo real:
```text
INFO - Analytics - 🔥 - Trailing Stop atingido para BTC-USDT! | A (TP): 2 | B (SL): 1 | C (TS): 1 | Total: 4 | Success Rate: 75.00%
```

---

## 🔍 Análise Técnica (Opcional)

Antes de executar um sinal, o bot pode filtrar operações contra a tendência via `analise_tecnica.py`:

- **Timeframes analisados:** 15m, 1h e 4h
- **Indicadores:** EMA 9, EMA 21 e EMA 50
- **Critério:** Os 3 timeframes devem estar alinhados na direção do sinal (LONG ou SHORT)
- **Filtro de volume:** Volume recente deve ser superior à média dos últimos 20 candles

Para **desabilitar** a análise técnica:
```properties
use_technical_analysis=false
```

---

## ⚙️ Configuração

### 1. `config.properties`

```properties
# Credenciais da BingX
bingx_api_key=SUA_API_KEY
bingx_secret_key=SUA_SECRET_KEY
bingx_api_url=https://open-api.bingx.com
bingx_api_url_testnet=https://open-api-vst.bingx.com

# Credenciais do Telegram
api_id=SEU_API_ID
api_hash=SEU_API_HASH
group_id=ID_DO_GRUPO
session_name=minha_sessao

# Parâmetros de Trade
trade_percentage=3
use_technical_analysis=false
```

### 2. Variáveis de Ambiente (`.env`)

| Variável                 | Padrão  | Descrição |
|--------------------------|---------|-----------|
| `TRADE_PERCENTAGE`       | `3`     | % do saldo por operação |
| `TRAILING_STOP_RATE`     | `1.5`   | Callback do Trailing Stop em % |
| `USE_TECHNICAL_ANALYSIS` | `false` | Habilita/desabilita filtro técnico |
| `PORT_EXECUTOR`          | `8001`  | Porta do TradeExecutor Flask |
| `IS_TESTNET`             | `false` | Usa Testnet ou Mainnet |

### 3. Requisitos obrigatórios na BingX
> ⚠️ **O bot só funciona com estas configurações na corretora:**
> - **Margin Mode:** `CROSS` (Cruzada)
> - **Position Mode:** `ONE-WAY` (Uma direção)

---

## 🚀 Como Executar

```bash
# Instalar dependências
pip install -r requirements.txt

# Testnet
python start_all.py --testnet

# Produção
python start_all.py --mainnet
```

### Como serviço systemd

```bash
sudo cp tradebot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start tradebot
sudo journalctl -u tradebot -f
```

### Logs
```bash
tail -f logs/app.log
```

---

## 📁 Estrutura do Projeto

```
TelegramReader/
├── TelegramReader.py        # Leitor de mensagens do Telegram (Telethon)
├── TradeExecutor.py         # API Flask — executa trades e ajusta proteções
├── PositionMonitor.py       # Daemon de monitoramento de posições abertas
├── analise_tecnica.py       # Filtro técnico (EMA + Volume)
├── start_all.py             # Orquestrador dos 3 processos
├── utils.py                 # Parser de mensagens, utilitários e analytics
├── config.properties        # Configurações principais
├── active_trades.json       # Estado de TPs ativos por símbolo (git ignored)
├── trade_analytics.json     # Acumulador de métricas A/B/C (git ignored)
├── tradebot.service         # Unit file do systemd
├── integration/
│   └── BingXBroker.py       # Client da API BingX Futures
├── message/
│   ├── mensagem_sinal.py    # Model de sinal de entrada
│   └── mensagem_tp.py       # Model de atualização de TP
├── log/
│   └── logger_config.py     # Configuração de logging
└── logs/
    └── app.log              # Log rotativo da aplicação
```

---

## 📝 Observações Importantes

- **Sinais com TPs iguais** (ex: TP1 = TP2 = TP3 = TP4): A BingX pode executar todas as ordens de uma vez. O `PositionMonitor` detectará `0 TPs restantes` e ativará o Trailing Stop diretamente.
- **Slippage**: Em ativos de preço muito baixo, a BingX pode rejeitar ordens com `101400: TP Price must be greater than Last Price`. O bot loga o erro e continua com as ordens seguintes.
- **active_trades.json**: Não apagar durante operação. É ignorado pelo git.

---

---

# English (UK)

A bot that reads trading signals from a private Telegram group and automatically executes them on the **BingX Futures** exchange, with progressive risk management via Break Even and Trailing Stop.

---

## 🗺️ Architecture Overview

The system comprises **3 independent services** running in parallel, managed by `start_all.py` (or via `systemd`):

```
┌─────────────────────────────────────────────────────────────┐
│                        Telegram Group                       │
│              (Entry signals + TP update messages)           │
└───────────────────────────┬─────────────────────────────────┘
                            │ Message received
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    TelegramReader.py                        │
│  • Listens to messages via Telethon                         │
│  • Classifies: SIGNAL (new trade) or MONITORING (TP hit)    │
│  • POST /trade  →  TradeExecutor                            │
│  • PUT  /tp     →  TradeExecutor                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP (localhost)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    TradeExecutor.py                         │
│  Flask API port 8001                                        │
│  POST /trade → Opens 5 orders on BingX                      │
│  PUT  /tp    → Adjusts SL (Break Even) or activates TS      │
└───────────────────────────┬─────────────────────────────────┘
                            │ BingX API
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   PositionMonitor.py                        │
│  • Polling daemon (every 15s)                               │
│  • Independent fallback from Telegram                       │
│  • Detects executed TPs via open order count                │
│  • Automatically applies Break Even and Trailing Stop       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Execution Strategy — 5 Orders per Signal

Each received signal opens **5 simultaneous market orders** with specific proportions of the allocated capital:

| Order | Volume | Fixed TP  | SL | Action when hit |
|-------|--------|-----------|----|-----------------|
| #1    | 10%    | TP1       | ✅ | Move SL → Break Even |
| #2    | 20%    | TP2       | ✅ | Move SL → Break Even (if not already set) |
| #3    | 50%    | TP3       | ✅ | Move SL → Break Even (if not already set) |
| #4    | 10%    | TP4       | ✅ | Activate Trailing Stop for the remaining 10% |
| #5    | 10%    | ❌ None   | ✅ | Tracked **only** by the Trailing Stop |

> **The 10% for Order #5 remains open without a fixed TP**, waiting for the Trailing Stop which is activated when Order #4 (TP4) is hit. This captures any further upside movement beyond TP4 without capping profits.

---

## 🛡️ Progressive Risk Management

### Sequence of events after position entry

```
Entry
  │
  ├─ TP1 hit (10% closed)
  │     └─► SL for all orders → BREAK EVEN (entry price)
  │          ✅ From this point, worst case = flat trade
  │
  ├─ TP2 hit (20% closed)
  │     └─► Confirms SL at Break Even (if not already applied)
  │
  ├─ TP3 hit (50% closed)
  │     └─► Confirms SL at Break Even (if not already applied)
  │
  ├─ TP4 hit (10% closed)
  │     └─► TRAILING STOP activated on remaining 10% (Order #5)
  │          • Follows price with configurable callback (default: 1.5%)
  │          • Captures additional movement without a fixed TP
  │
  └─ Trailing Stop triggered
        └─► Position #5 automatically closed by the exchange
```

### Anti-Race Condition (PositionMonitor)
The `PositionMonitor` implements a **5-second debounce**: before taking action, it re-queries the API to confirm the TP count has genuinely changed. This prevents erroneous actions caused by API latency or concurrent order executions.

### State Detection (Stateless)
The system is **stateless** — no database is used. The monitoring logic works as follows:

- `TradeExecutor` saves to `active_trades.json` **how many fixed-price TPs** were opened (e.g. `"VELVET-USDT": 4`)
- `PositionMonitor` queries the API and counts the open `TAKE_PROFIT_MARKET` orders (fixed TPs) still remaining
- The difference between the expected and actual count reveals which TP was hit, triggering protections and the Trailing Stop for the 5th order

| Remaining Fixed TPs Open         | Detected Situation | Applied Action |
|-----------------------------------|--------------------|----------------|
| `expected - 1`                    | TP1 hit            | Move Stop Loss to Break Even |
| `expected - 2`                    | TP2 hit            | Ensure Stop Loss is at Break Even |
| `expected - 3`                    | TP3 hit            | Ensure Stop Loss is at Break Even |
| `0` (All fixed TPs hit)           | TP4 hit            | Cancel SL and activate Trailing Stop on Order #5 (remaining 10%) |

> 💡 **Note on the 5 Orders:** Of the 5 orders opened per signal, only the first 4 have fixed Take Profits (TP1–TP4). The 5th order is opened without a fixed TP and is managed exclusively by the Trailing Stop, which activates once the 4th order (TP4) is liquidated.

---

## 📊 Trade Outcome Analytics

The bot features a persistent, real-time performance telemetry system, consolidating metrics in the local `trade_analytics.json` file.

### Metrics and Classification

Trades are classified into three distinct outcome types:

* **A (`tp_hits`):** Incremented each time a fixed Take Profit (TP1–TP4) is successfully executed on the exchange.
* **B (`sl_hits`):** Incremented when a position is closed by the original Stop Loss or at Break Even.
* **C (`trailing_hits`):** Incremented when the remaining 10% (Order #5) is closed by the Trailing Stop.

### Success Rate

```
Success Rate = (A + C) / (A + B + C) × 100
```

### Operational Flow
- **Persistence:** Metrics are written to `trade_analytics.json` and survive service restarts.
- **Exit Detection:** `PositionMonitor` compares active positions on the exchange against `active_trades.json` and determines exit type via the `_ts_active` flag.
- **Shutdown Report (`atexit`):** When the `TradeExecutor` shuts down, a final consolidated summary is written to `app.log`.

Example real-time log entry:
```text
INFO - Analytics - 🔥 - Trailing Stop hit for BTC-USDT! | A (TP): 2 | B (SL): 1 | C (TS): 1 | Total: 4 | Success Rate: 75.00%
```

---

## 🔍 Technical Analysis (Optional)

Before executing a signal, the bot can filter out counter-trend trades via `analise_tecnica.py`:

- **Timeframes analysed:** 15m, 1h and 4h
- **Indicators:** EMA 9, EMA 21 and EMA 50
- **Criterion:** All 3 timeframes must align with the signal direction (LONG or SHORT)
- **Volume filter:** Recent volume must exceed the average of the last 20 candles

To **disable** technical analysis:
```properties
use_technical_analysis=false
```

---

## ⚙️ Configuration

### 1. `config.properties`

```properties
# BingX Credentials
bingx_api_key=YOUR_API_KEY
bingx_secret_key=YOUR_SECRET_KEY
bingx_api_url=https://open-api.bingx.com
bingx_api_url_testnet=https://open-api-vst.bingx.com

# Telegram Credentials
api_id=YOUR_API_ID
api_hash=YOUR_API_HASH
group_id=GROUP_ID
session_name=minha_sessao

# Trade Parameters
trade_percentage=3
use_technical_analysis=false
```

### 2. Environment Variables (`.env`)

| Variable                 | Default | Description |
|--------------------------|---------|-------------|
| `TRADE_PERCENTAGE`       | `3`     | % of balance per trade |
| `TRAILING_STOP_RATE`     | `1.5`   | Trailing Stop callback % |
| `USE_TECHNICAL_ANALYSIS` | `false` | Enables/disables technical filter |
| `PORT_EXECUTOR`          | `8001`  | TradeExecutor Flask port |
| `IS_TESTNET`             | `false` | Uses Testnet or Mainnet |

### 3. Mandatory BingX Requirements
> ⚠️ **The bot only functions correctly with the following exchange settings:**
> - **Margin Mode:** `CROSS`
> - **Position Mode:** `ONE-WAY`

---

## 🚀 How to Run

```bash
# Install dependencies
pip install -r requirements.txt

# Testnet
python start_all.py --testnet

# Production (Mainnet)
python start_all.py --mainnet
```

### As a systemd service

```bash
sudo cp tradebot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start tradebot
sudo journalctl -u tradebot -f
```

### Logs
```bash
tail -f logs/app.log
```

---

## 📁 Project Structure

```
TelegramReader/
├── TelegramReader.py        # Telegram message reader (Telethon)
├── TradeExecutor.py         # Flask API — executes trades and adjusts protections
├── PositionMonitor.py       # Polling daemon for monitoring active positions
├── analise_tecnica.py       # Technical filter (EMA + Volume)
├── start_all.py             # Orchestrator for all 3 processes
├── utils.py                 # Message parser, utilities and analytics
├── config.properties        # Main configuration file
├── active_trades.json       # Active TP state per symbol (git ignored)
├── trade_analytics.json     # Persistent A/B/C metrics accumulator (git ignored)
├── tradebot.service         # Systemd service unit file
├── integration/
│   └── BingXBroker.py       # BingX Futures API client
├── message/
│   ├── mensagem_sinal.py    # Entry signal model
│   └── mensagem_tp.py       # TP update model
├── log/
│   └── logger_config.py     # Logging configuration
└── logs/
    └── app.log              # Rotating application log file
```

---

## 📝 Important Notes

- **Signals with matching TPs** (e.g. TP1 = TP2 = TP3 = TP4): BingX may execute all orders simultaneously. The `PositionMonitor` will detect `0 remaining TPs` and activate the Trailing Stop directly.
- **Slippage**: On very low-priced assets, BingX may reject orders with `101400: TP Price must be greater than Last Price`. The bot logs the error and continues with the remaining orders.
- **active_trades.json**: Do not delete during operation. This file is ignored by git.