# TradingDash — handoff técnico (para humanos e IAs)

Este arquivo é a **fonte de continuidade** do projeto.  
O `README.md` é a porta de entrada para **rodar e usar** o app.  
Use **este `PROJECT.md`** para entender arquitetura, decisões, limitações e o que falta implementar.

> **Não é recomendação de investimento.** App educacional / paper trading na B3.

---

## 1. Visão do produto

**Nome:** TradingDash  
**Repo:** https://github.com/dyegomiranda/Trading-Dash  
**Objetivo:** ajudar iniciantes a estudar a tese **Quality Dividend** (empresas de qualidade + dividendos sustentáveis + reinvestimento), com:

1. Ranking / score de ações B3  
2. Carteira **paper money** (dinheiro fictício)  
3. Projeção de renda (dividendos)  
4. **Simulação histórica** (“e se eu tivesse seguido a tese desde a data X?”)  
5. Overview com as 4 notas da tese e **notícias reais** (links)

**Persona:** usuário iniciante em português (Brasil); UI deve ser autoexplicativa.

**Tese (resumo):**
- Qualidade (ROE/ROIC, margens, FCF)
- Dividendos sustentáveis (DY preferencial ~4–12%, payout saudável)
- Saúde financeira (alavancagem)
- Valuation razoável
- Core ~70% / satélite ~30%

---

## 2. Stack e como rodar

| Item | Valor |
|------|--------|
| Linguagem | Python 3.12+ (testado em 3.14) |
| UI | Streamlit ≥ 1.61 |
| Dados | yfinance + provider demo sintético |
| Charts | Plotly |
| Shell do usuário | frequentemente **fish** (usar `.venv/bin/streamlit`, não só `source activate`) |

```bash
git clone https://github.com/dyegomiranda/Trading-Dash.git
cd Trading-Dash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

**Entrypoint:** `app.py`  
**Navegação:** `st.navigation(..., position="hidden")` + menu custom em `src/ui/shell.py` (`render_sidebar_nav`) — logo **acima** dos `st.page_link`.

---

## 3. Estrutura do repositório

```
TradingDash/
  app.py                 # router + sidebar custom
  app_pages/
    inicio.py            # overview
    descobrir_acoes.py   # ranking + histórico de preços
    minha_carteira.py    # paper portfolio
    teste_no_passado.py  # backtest
    guia.py              # dicionário / tese
    configuracoes.py     # modo treino, fonte B3, regime macro
  assets/logo/TD_logo.png
  assets/icon/TD_icon.png
  src/
    config.py            # pesos, universo B3, settings
    services.py          # helpers de app (format, load scored)
    data/
      providers.py       # Demo + YFinance + BrapiDataProvider
      providers_brapi.py # provider brapi.dev (fonte B3 nativa)
      universe.py        # tickers B3
      benchmarks.py      # CDI (BCB SGS serie 12)
      news.py            # Google News RSS + yfinance news (só com URL)
      pit_loader.py      # JSON point-in-time (semente ou CVM)
      cvm.py             # download/parse DFP/ITR/FCA
    thesis/scoring.py    # score, filtros, recommend_weights
    thesis/macro.py      # regime macro (Selic/IPCA) → inclinação setorial
    portfolio/
      paper.py           # PaperPortfolio (JSON em data/portfolio/)
      income.py          # projeção de renda
    backtest/engine.py   # walk-forward rebalance (custos, PIT, ADV, TTM DY)
    backtest/robustness.py  # Monte Carlo (bootstrap da curva)
    ui/
      shell.py           # branding + nav
      theme.py           # CSS dark fintech
      components.py      # KPIs, headers, cards
      charts.py          # plotly helpers
      wallet.py          # wallet balance / asset rows
      friendly.py        # labels PT, glossário
      paths.py           # ROOT / assets
  data/cache/            # cache JSON (gitignored conteúdo)
  data/portfolio/        # carteiras paper (gitignored *.json)
  PROJECT.md             # este arquivo
  README.md              # setup e uso
```

---

## 4. Fluxos principais

### 4.1 Scoring (`src/thesis/scoring.py`)
- `score_universe(fundamentals)` → DataFrame com `score_*`, `bucket`, `rank`
- **Importante:** remove colunas `score_*` / meta **antes** de recalcular (evita `score_total` duplicado)
- `recommend_weights` → `target_weight` core/satélite

### 4.2 Providers (`src/data/providers.py`)
- **`demo`:** fundamentals + preços + dividendos sintéticos (drift **não** amarrado ao ROE; queda ex-div no preço). Primeira visita da UI.  
- **`yfinance`:** B3 via `TICKER.SA`, cache em `data/cache/` — fonte principal da Bolsa real  
- **`brapi`:** experimental (preço/dividendo B3; ROE/dívida ausentes no plano grátis). Escondido no seletor, atrás de expander.

### 4.3 Paper portfolio (`src/portfolio/paper.py`)
- Persistência: `data/portfolio/{name}.json` (um arquivo por carteira)
- Múltiplas carteiras: `list_portfolios()` / `save_portfolio()` / `load_portfolio()` / `delete_portfolio()`
- `paper-main` é a carteira padrão protegida (não pode ser apagada)
- `set_capital`, `buy` / `sell` / `buy_value`, `rebalance_to_weights`
- UI em `minha_carteira.py`: trocador de carteira, criar nova, apagar (2 cliques), capital editável, aplicar tese, alocação manual, feedback em `st.session_state["pf_flash"]`

### 4.4 Histórico de score (`src/portfolio/score_history.py`)
- Ledger local das notas observadas: `data/scores/history.json` — `{ticker: [{"d": "YYYY-MM-DD", "s": ...}]}`
- Uma leitura por ticker por dia (a última do dia vence); retenção de 60 dias
- Alimenta o alerta de **deterioração/recuperação** de nota (`score_caindo`/`score_subindo`, ≥ 10 pts) na carteira
- **Honesto:** não é dado CVM point-in-time; é o que o app observou ao longo do uso (etiquetado como tal)

### 4.5 Backtest (`src/backtest/engine.py` + `src/backtest/export.py`)
- Rebalance **Q (padrão)** / M / A, equity curve, trades, dividends
- No rebalance: **preço = fechamento do dia** e **DY = TTM 12 meses** dos dividendos já pagos (anti look-ahead de mercado)
- Custos: `conservative_costs()` na UI (15+10 bps, JCP 25% do provento a 15%, IR 15% no ganho, slippage dinâmico, atraso 15d no crédito)
- ADV mínimo + teto de ordem vs ADV; saída por delistagem (sem preço)
- PIT: auto-injeta `data/reference/pit_snapshots.json` quando ligado. Campo `origin`: `seed_curated` (semente) ou `cvm_dfp_itr` (parse real)
- Monte Carlo: `src/backtest/robustness.py` (bootstrap da **própria** curva — não é previsão)
- **Exportação:** ZIP de CSVs + HTML imprimível; o PDF declara origem PIT e custos
- **Limitação:** a semente **não** é DFP/ITR. Promover com `scripts/download_cvm_data.py --download --build`

### 4.6 Config / dados de rede
- `src/data/yf_retry.py` — helper central de retry/backoff (exponencial + jitter) para chamadas de rede do yfinance (rate-limit 429, timeout, conexão). `set_retry_sleep(False)` desliga o sleep real para testes.
- `src/data/ttl.py` — TTL por tipo de dado (`ttl_for(kind, settings)`); `Settings.cache_ttl_kind_hours` sobrescreve `cache_ttl_hours` por tipo (benchmark 24h, macro/6h, fundamentals 12h, prices 6h, dividends 24h, brapi_quote 6h).

### 4.7 Notícias (`src/data/news.py`)
- Google News RSS + yfinance
- **Só** itens com `url` (sem fake)

### 4.8 Observabilidade (`src/monitoring.py`)
- Logs JSONL diários em `data/logs/{YYYY-MM-DD}.jsonl` (`gitignored`), com `timed()` para medir duração de fetches (fundamentals, preços, dividendos, indices, CDI), status de cache (hit/miss) e flag `slow` (> 5s)
- `coverage_event` registra a cobertura dos dados (preços/DY/ROE) usando o mesmo cálculo de `src/data/quality.py::coverage_summary` — útil para ver regressão de cobertura sem abrir a UI
- Tudo best-effort e silencioso (nunca levanta exceção / quebra o app); arquivos antigos (> 35 dias) são apagados automaticamente

### 4.9 Narrativa da tese (`src/thesis/narrative.py`)
- Gera texto curto em PT claro ("por que essa ação?") **sem IA**: `build_stock_narrative(row)` explica pilar a pilar (qualidade/ROE, dividendos/DY, dívida, preço) com honestidade quando falta dado, e `build_portfolio_summary(recs)` resume o que a lista representa
- Usada na página Descubra: resumo da lista (card logo após os KPIs) + expander "Por que essa ação?" por ticker

### 4.10 Internacionalização leve (`src/format_hooks.py`)
- Hook central de formatação (`format_num`, `format_brl_hook`, `format_pct_hook`) com separadores/símbolo por locale; `pt_BR` (padrão) ou `en_US`
- Config via `Settings.locale` (`LOCALE` no `.env`) + `set_active_locale`; `page_setup()` aplica automaticamente
- `src/services.format_pct`/`format_brl` delegam ao hook (migração incremental)

### 4.11 Deploy / pre-flight (`deploy/preflight.py`)
- Roda o mesmo contrato do Cloud (pip install `requirements.txt` + boot do `app.py`) **offline**: importa cada módulo de `src/`, compila `app_pages/`, confere `data/reference/b3_tickers.json` versionado e sobe o app com `streamlit.testing.v1.AppTest` com a fonte forçada para `demo`
- Presente no CI (passo `Deploy pre-flight`) e na suíte (`tests/test_preflight.py`); uso: `python deploy/preflight.py`
- `README.md` documenta deploy no Streamlit Community Cloud + segredos opcionais (`BRAPI_TOKEN`, `XAI_API_KEY`)

### 4.12 Contrato de dados (`src/data/schemas.py`)
- `FUNDAMENTALS_SCHEMA` — colunas/dtypes do snapshot fundamentalista (as 3 fontes + scoring + backtest trocam o mesmo contrato)
- `FUNDAMENTALS_REQUIRED` — mínimo para scoring significativo (ticker, name, sector, price, roe, dividend_yield), reportado, não bloqueia
- `coerce_fundamentals`/`coerce_ohlcv` — fronteira única de normalização: remove duplicadas, preenche ausentes com NaN, força dtype numérico/bool; **nunca levanta exceção** (violação vira evento em `data/logs` via monitoring)
- Pontos de uso: início de `score_universe` (choke point de todas as fontes/backtest) e histórico de preço na UI (Descobrir)

### 4.13 Dependências pinadas (`requirements.txt` + `requirements.lock`)
- `requirements.txt` — faixas compatíveis com o ambiente testado (`pandas>=2.1,<3.1`, `numpy>=1.26,<3.0`, etc.); é o que o Streamlit Cloud resolve
- `requirements.lock` — snapshot congelado da resolução que passou na suíte (reprodução exata: `pip install -r requirements.lock`)
- `scripts/check_lock.py` — guarda de regressão: versões instaladas ≥ lock; roda no CI e na suíte (`tests/test_lock.py`)

### 4.8 UI / branding
- Tema dark fintech, sidebar cor `#080714` (blend com fundo do logo)
- Logo grande acima do menu (menu nativo hidden + `st.page_link`)
- Sem texto “TradingDash” sob o logo

---

## 5. Páginas (comportamento esperado)

| Página | Arquivo | Deve fazer |
|--------|---------|------------|
| Início | `inicio.py` | KPIs carteira, rosca, 4 notas da tese, headlines reais |
| Descubra ações | `descobrir_acoes.py` | ranking, pesos, histórico de preço por ticker |
| Minha carteira | `minha_carteira.py` | dashboard, operar (capital + tese + manual), renda, mais |
| Teste no passado | `teste_no_passado.py` | onboarding explicativo (Modo treino vs Bolsa real) **antes** do 1º run; depois KPIs + gráficos |
| Guia | `guia.py` | glossário, fontes de dados e pesos da tese |
| Configurações | `configuracoes.py` | modo treino, brapi, regime macro, atualizar cache |

---

## 6. Glossário de UI (PT)

| Termo na UI | Significado técnico |
|-------------|---------------------|
| Modo treino | Provider `demo` |
| Bolsa real | Provider `yfinance` (brapi é experimental) |
| Nota | `score_total` 0–100 |
| Base / Complemento | `bucket` core / satellite |
| Montar carteira com a tese | `score_universe` (filtro da tese) + `recommend_weights` + `rebalance_to_weights` |

---

## 7. Decisões de design já tomadas

1. Streamlit (não React) no MVP  
2. Paper money first; capital editável  
3. Universo amplo filtrado (lista em `config.B3_UNIVERSE`)  
4. UI dark fintech (Exodus / trading dashboard)  
5. Linguagem para iniciantes (labels em `friendly.py`)  
6. Menu custom (logo acima dos links)  
7. Headlines reais com links, sem filler fake  

---

## 8. Problemas já resolvidos (não reintroduzir)

| Bug | Causa | Fix |
|-----|-------|-----|
| `score_total` not unique | rescore em DF já pontuado / concat | strip scores + assign colunas em `scoring.py` |
| `DataFrame.tolist` em rosca | rename criou `market_value` duplicado | `value_col` seguro em `charts.holdings_donut` |
| `StreamlitValueBelowMinError` 999.99 | float no capital | clamp + min 100 + limpa session_state |
| Logo abaixo do menu | `st.navigation` renderiza nav no topo | `position="hidden"` + `st.page_link` após logo |
| Dois logos | `st.logo` + `st.image` | só logo custom; esconde nativo |
| `timedelta` `NameError` em Descobrir | import removido ao trocar `datetime.utcnow` por `utcnow()` | reimportar `timedelta` em `app_pages/descobrir_acoes.py` |
| Real rate macro negativo (-4,3%) | SGS 11 (Selic) chega em **fração anual**; SGS 433 (IPCA) em **% mensal** | normalizar (`selic*100` e acumular IPCA 12m) em `macro.py` |
| Dividendo creditado para quem comprou entre ex e pagamento | entitlement checado contra `paymentDate` | usar `ex_date` da fonte (`exDate`; `lastDatePrior` = data-com → ex+1d); **nunca** paymentDate; posição na véspera da data-ex |
| Selic ~5% em 2026 (regime invertido) | SGS 11 é % ao dia, tratado como fração anual | SGS **432** (meta Copom, % a.a.) |
| “Dívida forte” com 3x EBITDA | `_strength_score` maior=melhor aplicado à dívida | buckets explícitos (caixa / confortável / esticada / preocupante) |
| TAEE11/SANB11 como FII | regex `XXXX11` | cadastro + universo da tese = ação; FII por nome/lista |
| Nota 50 com dado faltando | pilar vazio devolvia 50 | pilar ausente = None; renormaliza pesos; sugestão exige ROE+DY+(payout/FCF) |
| Filtro da tese só no toggle “rigoroso” | default frouxo + fallback para universo sem filtro | default = tese; frouxo é opt-in; sem fallback silencioso |
| Criar carteira a cada tecla | text_input gravava na hora | botão **Criar**; atualiza `pf_select` |
| Estimativa mensal no caixa | `allow_monthly_estimate=True` | default False; renda projetada não mexe no cash |

---

## 9. O que ainda precisa ser implementado (backlog)

Priorize com o usuário; itens em **negrito** são alto valor.

### Dados e tese
- [x] Cadastro B3 de **nome/setor** (`data/reference/b3_tickers.json` + `reference.py`) — demo **não inventa setor**  
- [x] Renomeações conhecidas (ELET3→AXIA3) no universo  
- [x] Default da UI: **Bolsa real**; demo com banner de risco  
- [x] Gancho PIT no backtest (`fundamentals_by_date` + auto-load + DY TTM do dia)  
- [~] **Parse CVM DFP/ITR de verdade** — script `scripts/download_cvm_data.py --download --build` + `src/data/cvm.py`. O JSON versionado ainda é **semente curada** (`origin=seed_curated`) até alguém rodar o download (ZIPs grandes, rede)  
- [ ] Melhor cobertura de indicadores BR (JCP, payout real, etc.)  
- [x] Fonte B3 dedicada (brapi) — **experimental**, sem ROE/dívida no plano grátis; Yahoo continua principal  
- [ ] Revisão humana periódica do JSON de tickers  
- [x] Setores da base (utilities, bancos, telecom, consumo básico) explícitos na UI (`render_core_sectors_card`)  — não é lista BESST fechada

### Simulação / risco
- [x] **Benchmark** na simulação (Ibovespa + CDI + **IDIV** opcional) — `src/data/benchmarks.py` + UI; `fetch_idiv_close` + `include_idiv` em `BacktestConfig`  
- [x] Custos conservadores na UI — 15+10 bps, JCP 25%, IR 15% no ganho, slippage dinâmico, atraso 15d (`conservative_costs()`)
- [x] Filtro de liquidez **ADV** + teto de ordem vs ADV (`max_adv_order_pct`)
- [x] Monte Carlo bootstrap da curva (`src/backtest/robustness.py`) — faixa P10/P50/P90 **desta** amostra, sem fingir previsão
- [x] Universo histórico no ensaio (`include_historical` / `B3_HISTORICAL_EXTRA`) — reduz viés de sobrevivência
- [x] Regras de saída simples (score, DY, payout, dívida, FCF) — `src/thesis/alerts.py`  
- [x] Regras de saída avançadas: alerta de **histórico de score** (nota caiu/subiu ≥ 10 pts entre observações) — ledger local em `data/scores/history.json` (`src/portfolio/score_history.py`) + códigos `score_caindo`/`score_subindo` em `src/thesis/alerts.py` + labels PT em `src/ui/friendly.py`  
- [ ] Regras de saída avançadas: rating, eventos CVM  
- [x] Export CSV/PDF do relatório de backtest — `src/backtest/export.py` (ZIP de CSVs + HTML imprimível → PDF no navegador) + botões em `teste_no_passado.py`  

### Carteira
- [x] Editar peso % por ativo de forma visual (sliders) — aba “Ajuste fino · pesos-alvo por ação (%)” em `minha_carteira.py`  
- [x] Múltiplas carteiras com UI de troca (trocar, criar, apagar) — `data/portfolio/{nome}.json`  
- [x] Projeção de renda com **reinvestimento** explícito — gráfico “Bola de neve” (reinvestir vs sacar) em `minha_carteira.py` + `snowball_chart` em `src/ui/charts.py`  
- [x] Dividendos creditados no paper “ao vivo” com **data-ex real** — `src/portfolio/dividends_live.py` (`sync_paper_dividends` usa `ex_date` da fonte; quem compra no dia da data-ex não recebe)  
- [x] Alertas quando score/fundamentals de holding piora — Dashboard da carteira

### IA / contexto
- [x] Narrativa da tese “por que essa ação?” em PT claro (sem IA) — `src/thesis/narrative.py` + página Descubra · testes em `tests/test_narrative.py`  
- [x] Camada de IA opcional (coach no Início + fallback local); resumo de notícias/ticker ainda sem UI  
- [x] Regime macro (meta Selic SGS **432** % a.a. + IPCA 12 prints) — seletor **compartilhado** na sessão; backtest **não** aplica o regime de hoje

### UX / produto
- [x] Onboarding na primeira visita (session_state no Início; reset no Início e no Guia) — não persiste entre browsers 
- [x] Explicar “Modo treino” em **todas** as páginas com o seletor (`src/ui/data_source.py`)  
- [x] Testes automatizados (pytest) para scoring, portfolio, backtest — `tests/` (144 testes, rede mockada) 
- [x] CI no GitHub (lint + testes) — `.github/workflows/ci.yml` (matrix Python 3.12/3.13/3.14 + `ruff check src/ tests/` + `pytest tests/ -q`)  
- [x] Instruções de deploy Streamlit Community Cloud no README  
- [x] Pre-flight de deploy (app sobe offline) — `deploy/preflight.py` (AppTest, fonte demo) + CI + `tests/test_preflight.py`  
- [ ] Deploy efetivo (conectar conta no share.streamlit.io) — falta conta/servidor do dono  
- [ ] Docker opcional  

### Qualidade
- [x] Observabilidade: logs de tempo e cobertura — `src/monitoring.py` (JSONL diário em `data/logs/`, `timed()` por fetch, `cache_hit`, `coverage_event`) · testes em `tests/test_monitoring.py`  
- [x] Tipagem e validação mais rígidas nos DataFrames — `src/data/schemas.py` (`FUNDAMENTALS_SCHEMA` + `coerce_fundamentals`/`coerce_ohlcv` na fronteira de `score_universe` e do histórico na UI; nunca quebra, violação vira evento de observabilidade) · testes em `tests/test_schemas.py`  
- [x] Tratar rate-limit yfinance com backoff/retry — `src/data/yf_retry.py` (`fetch_with_retry`, jitter exponencial; envolve `yf.download`, `tk.info`, `tk.dividends`, `tk.news`) · testes em `tests/test_yf_retry.py`  
- [x] Internacionalização leve (hook de formato/locale) — `src/format_hooks.py` + `Settings.locale` · testes em `tests/test_format_hooks.py`  
- [x] Pinned deps + lock de reprodução — `requirements.txt` com faixas testadas (pandas<3.1, numpy<3.0) + `requirements.lock` (snapshot congelado) + guarda `scripts/check_lock.py` no CI (`tests/test_lock.py`)

---

## 10. Convenções para a próxima IA

1. **Não** reintroduzir `st.logo` nativo pequeno + logo grande.  
2. **Não** usar `pages/` auto-discovery; manter `app_pages/` + `app.py`.  
3. Ao recalcular score, **sempre** limpar colunas `score_*` / usar `score_universe` atual.  
4. Preferir labels em português via `friendly.py`.  
5. Shell do usuário pode ser **fish** — documentar comandos com `.venv/bin/...`.  
6. Push: repo `dyegomiranda/Trading-Dash`, branch `main`.  
7. Atualize **este `PROJECT.md`** quando fechar ou abrir itens de backlog.  
8. Atualize o `README.md` para usuários finais (setup + features), sem excesso de detalhe interno.

---

## 11. Comandos úteis

```bash
# rodar
.venv/bin/streamlit run app.py

# smoke score + rebalance
.venv/bin/python -c "from src.data.providers import get_provider; from src.thesis.scoring import score_universe, recommend_weights; f=get_provider('demo').get_fundamentals(); s=score_universe(f); print(len(s.filtered), recommend_weights(s.filtered).head(3))"

# git
git status
git add -A && git commit -m "..." && git push origin main
```

---

## 12. Contato / ownership

- Dono do repo GitHub: **dyegomiranda**  
- Projeto iniciado a partir de conversa de produto (tese Quality Dividend / Barsi-like refinada) e implementação iterativa em Streamlit.

---

## 13. Plano de robustez da simulação (A–D)

Objetivo: subir a **honestidade** do laboratório, não fingir um backtest auditável de fundo.

| Fase | O quê | Status |
|------|--------|--------|
| **A** | Defaults conservadores (rebalance Q, custos com JCP+IR no ganho, universo histórico, haircut de yield, P10/P50/P90 na renda, copy/PDF honestos, DY TTM no rebalance) | **Feito** (2026-08-20) |
| **B** | PIT contábil de verdade: parser CVM DFP/ITR + ADV + Monte Carlo + cash lag + slippage dinâmico | Motor/UI/script **feitos**; JSON versionado ainda é **semente** até `--download --build` |
| **C** | Combinatorial purged CV / walk-forward OOS, Piotroski/BSD como *overlay* opcional, não como tese nova | **Não iniciado** |
| **D** | Fonte paga (fundamentus/status invest/comercial) se a semente CVM não bastar | **Não iniciado** |

**Teto honesto de confiança** (seguir a tese no app, paper money): ~50–65/100 com CVM parseada + custos + TTM; ~35–50/100 com a semente. Nunca 90+.

Como promover o PIT:
```
.venv/bin/python scripts/download_cvm_data.py --years 2020-2025 --download
.venv/bin/python scripts/download_cvm_data.py --years 2020-2025 --build
```
A CVM **não** publica preço nem DY — o motor completa com o pregão do dia.

---

*Última atualização do handoff: 2026-08-20 (Fase A completa + parser CVM; semente PIT ainda não é DFP/ITR).*
