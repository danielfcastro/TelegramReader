# 📡 TelegramReader — Bot de Trading Automatizado com Gestão de Risco

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

| Ordem | Volume | TP Fixo | SL | Ação ao ser atingida |
|-------|--------|---------|-----|----------------------|
| #1    | 10%    | TP1     | ✅  | Move SL → Break Even |
| #2    | 20%    | TP2     | ✅  | Move SL → Break Even (se não estiver) |
| #3    | 50%    | TP3     | ✅  | Move SL → Break Even (se não estiver) |
| #4    | 10%    | TP4     | ✅  | Ativa Trailing Stop para os 10% restantes |
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
- O `PositionMonitor` consulta a API e conta os `TAKE_PROFIT_MARKET` ainda abertos
- A diferença entre o esperado e o atual revela qual TP foi atingido

| TPs Abertos Restantes | Situação detectada | Ação |
|-----------------------|-------------------|------|
| `expected - 1`        | TP1 atingido      | Break Even |
| `expected - 2`        | TP2 atingido      | Break Even (se não ativo) |
| `expected - 3`        | TP3 atingido      | Break Even (se não ativo) |
| `0`                   | TP4 atingido      | Trailing Stop |

---

## 📊 Trade Outcome Analytics

O bot possui um sistema de telemetria de performance persistente e em tempo real. Ele monitora a taxa de sucesso das operações consolidando as métricas no arquivo local `trade_analytics.json`.

### Métricas e Classificação

Os trades são classificados em três tipos de desfechos distintos:
* **A (TP Hits / `tp_hits`):** Incrementado a cada Take Profit fixo (TP1, TP2, TP3, TP4) executado com sucesso na corretora.
* **B (SL Hits / `sl_hits`):** Incrementado quando a posição é encerrada pelo Stop Loss original ou no Break Even.
* **C (TS Hits / `trailing_hits`):** Incrementado quando os 10% finais da posição (gerenciados pelo Trailing Stop pós-TP4) são fechados pelo Trailing Stop.

### Taxa de Sucesso (Success Rate)

A taxa de sucesso consolidada da estratégia é calculada dinamicamente pela fórmula:

$$Success\ Rate = \frac{A + C}{A + B + C} \times 100$$

### Funcionamento e Logs em Tempo Real
- **Persistência Stateless:** As métricas são salvas diretamente em `trade_analytics.json`, o que significa que o bot mantém a exatidão estatística histórica mesmo entre restarts de serviços.
- **Detecção de Saída:** O daemon `PositionMonitor` identifica quando uma posição ativa foi completamente fechada na corretora comparando-a com `active_trades.json` e determina o tipo de saída através do status do flag `_ts_active` do símbolo.
- **Relatório de Desligamento (`atexit`):** Ao encerrar o servidor Flask `TradeExecutor`, um hook final registra no `app.log` o resumo acumulado de toda a performance histórica do robô.

Exemplo de log gravado em tempo real no `logs/app.log`:
```text
2026-06-02 18:34:23,720 - INFO - Analytics - registrar_saida_trade - 🔥 - Trailing Stop atingido para BTC-USDT! | A (TP): 2 | B (SL): 1 | C (TS): 1 | Total: 4 | Success Rate: 75.00%
```

---

## 🔍 Análise Técnica (Opcional)

Antes de executar um sinal, o bot pode filtrar operações contra a tendência via `analise_tecnica.py`:

- **Timeframes analisados:** 15m, 1h e 4h
- **Indicadores:** EMA 9, EMA 21 e EMA 50
- **Critério:** Os 3 timeframes devem estar alinhados na direção do sinal (LONG ou SHORT)
- **Filtro de volume:** Volume recente deve ser superior à média dos últimos 20 candles

Para **desabilitar** a análise técnica e executar todos os sinais diretamente:

```properties
# config.properties
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
trade_percentage=3        # % do saldo disponível por sinal
use_technical_analysis=false
```

### 2. Variáveis de Ambiente (`.env` — gerado automaticamente)

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `TRADE_PERCENTAGE` | `3` | % do saldo por operação |
| `TRAILING_STOP_RATE` | `1.5` | Callback do Trailing Stop em % |
| `USE_TECHNICAL_ANALYSIS` | `false` | Habilita/desabilita filtro técnico |
| `PORT_EXECUTOR` | `8001` | Porta do TradeExecutor Flask |
| `IS_TESTNET` | `false` | Usa Testnet ou Mainnet |

### 3. Requisitos obrigatórios na BingX
> ⚠️ **O bot só funciona com estas configurações na corretora:**
> - **Margin Mode:** `CROSS` (Cruzada)
> - **Position Mode:** `ONE-WAY` (Uma direção)

---

## 🚀 Como Executar

### Instalação de dependências
```bash
pip install -r requirements.txt
```

### Execução manual

```bash
# Ambiente de testes (Testnet)
python start_all.py --testnet

# Ambiente de produção (Mainnet)
python start_all.py --mainnet
```

### Como serviço systemd (produção)

```bash
# Instalar o serviço
sudo cp tradebot.service /etc/systemd/system/
sudo systemctl daemon-reload

# Iniciar / Parar / Reiniciar
sudo systemctl start tradebot
sudo systemctl stop tradebot
sudo systemctl restart tradebot

# Ver status e logs em tempo real
sudo systemctl status tradebot
sudo journalctl -u tradebot -f
```

### Logs da aplicação
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
├── utils.py                 # Parser de mensagens e utilitários
├── config.properties        # Configurações principais
├── active_trades.json       # Estado ativo (ignorado pelo git)
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

## 📊 Fluxo Completo de um Sinal

```
1. Telegram → mensagem com símbolo, tipo (LONG/SHORT),
               alavancagem, SL, TP1, TP2, TP3, TP4

2. TelegramReader classifica como SINAL
   └─► POST /trade para TradeExecutor

3. TradeExecutor:
   a. [Opcional] Análise Técnica (EMA 15m/1h/4h + Volume)
   b. Verifica margem → força CROSS se necessário
   c. Calcula quantidade total = saldo × TRADE_PERCENTAGE%
   d. Abre 5 ordens de mercado:
      - Ordem 1 (10%): TP1 + SL
      - Ordem 2 (20%): TP2 + SL
      - Ordem 3 (50%): TP3 + SL
      - Ordem 4 (10%): TP4 + SL
      - Ordem 5 (10%): SL apenas (sem TP fixo)
   e. Salva { "SYMBOL": 4 } em active_trades.json

4. PositionMonitor (a cada 15s):
   - Conta TAKE_PROFIT_MARKET abertas para cada símbolo ativo
   - Aplica Break Even ou Trailing Stop conforme tabela acima

5. TradeExecutor /tp (via Telegram, em paralelo):
   - TP1/2/3 → Break Even (verificando estado atual)
   - TP4     → Ativa Trailing Stop
```

---

## 🔧 Variáveis de Proteção

O `PositionMonitor` aplica as proteções **independentemente** do Telegram. Isso garante que mesmo que uma mensagem de TP não chegue (delay, queda do bot, etc.), o Break Even e o Trailing Stop ainda são ativados via polling.

Ambos os mecanismos (`/tp` endpoint e `PositionMonitor`) verificam o estado atual antes de agir:
- Já está no Break Even? → Não faz nada
- Trailing Stop já ativo? → Não sobrescreve

---

## 📝 Observações Importantes

- **Sinais com TPs iguais** (ex: TP1 = TP2 = TP3 = TP4): A BingX pode executar todas as ordens de uma vez, zerando o livro de TPs abertos antes que o bot detecte individualmente. O PositionMonitor detectará `0 TPs restantes` e ativará o Trailing Stop diretamente.

- **Slippage**: Em ativos de preço muito baixo (ex: `0.00017`), o preço de execução pode ser maior que o TP1 ou TP2 do sinal. Nesse caso a BingX rejeita a ordem com `101400: TP Price must be greater than Last Price`. O bot loga o erro e continua com as ordens seguintes.

- **active_trades.json**: Arquivo local que guarda `{ "SYMBOL": numero_de_tps }`. É ignorado pelo git (`.gitignore`). Não apagar durante operação.