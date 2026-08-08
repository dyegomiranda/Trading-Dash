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
5. Overview com radar da tese e **notícias reais** (links)

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
  assets/logo/TD_logo.png
  assets/icon/TD_icon.png
  src/
    config.py            # pesos, universo B3, settings
    services.py          # helpers de app (format, load scored)
    data/
      providers.py       # DemoDataProvider + YFinanceDataProvider
      universe.py        # tickers B3
      news.py            # Google News RSS + yfinance news (só com URL)
    thesis/scoring.py    # score, filtros, recommend_weights
    portfolio/
      paper.py           # PaperPortfolio (JSON em data/portfolio/)
      income.py          # projeção de renda
    backtest/engine.py   # walk-forward rebalance
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
- **`demo`:** fundamentals + preços + dividendos sintéticos determinísticos  
- **`yfinance`:** B3 via `TICKER.SA`, cache em `data/cache/`

### 4.3 Paper portfolio (`src/portfolio/paper.py`)
- Persistência: `data/portfolio/{name}.json`
- `set_capital`, `buy` / `sell` / `buy_value`, `rebalance_to_weights`
- UI em `minha_carteira.py`: capital editável, aplicar tese, alocação manual, feedback em `st.session_state["pf_flash"]`

### 4.4 Backtest (`src/backtest/engine.py`)
- Rebalance M/Q, equity curve, trades, dividends
- **Limitação conhecida:** score fundamental **não** é point-in-time contábil completo (usa snapshot atual/demo + preços/divs históricos)

### 4.5 Notícias (`src/data/news.py`)
- Google News RSS + yfinance
- **Só** itens com `url` (sem fake)

### 4.6 UI / branding
- Tema dark fintech, sidebar cor `#080714` (blend com fundo do logo)
- Logo grande acima do menu (menu nativo hidden + `st.page_link`)
- Sem texto “TradingDash” sob o logo

---

## 5. Páginas (comportamento esperado)

| Página | Arquivo | Deve fazer |
|--------|---------|------------|
| Início | `inicio.py` | KPIs carteira, rosca, radar da tese, headlines reais |
| Descubra ações | `descobrir_acoes.py` | ranking, pesos, histórico de preço por ticker |
| Minha carteira | `minha_carteira.py` | dashboard, operar (capital + tese + manual), renda, mais |
| Teste no passado | `teste_no_passado.py` | onboarding explicativo (Modo treino vs Bolsa real) **antes** do 1º run; depois KPIs + gráficos |
| Guia | `guia.py` | glossário e pesos da tese |

---

## 6. Glossário de UI (PT)

| Termo na UI | Significado técnico |
|-------------|---------------------|
| Modo treino | Provider `demo` |
| Bolsa real | Provider `yfinance` |
| Nota | `score_total` 0–100 |
| Base / Complemento | `bucket` core / satellite |
| Aplicar sugestões da tese | `score_universe` + `recommend_weights` + `rebalance_to_weights` |

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

---

## 9. O que ainda precisa ser implementado (backlog)

Priorize com o usuário; itens em **negrito** são alto valor.

### Dados e tese
- [ ] **Fundamentals point-in-time** (CVM/ITR/DFP ou provedor pago) no backtest  
- [ ] Melhor cobertura de indicadores BR (JCP, payout real, etc.)  
- [ ] Fonte B3 dedicada (brapi, etc.) além de Yahoo  
- [ ] Setores preferenciais BESST mais explícitos na UI  

### Simulação / risco
- [ ] **Benchmark** na simulação (Ibovespa, IDIV, CDI)  
- [ ] Custos de corretagem, slippage, IR simplificado  
- [ ] Regras de saída (corte de dividendo, score caindo, rating downgrade)  
- [ ] Export CSV/PDF do relatório de backtest  

### Carteira
- [ ] Editar peso % por ativo de forma visual (sliders)  
- [ ] Múltiplas carteiras com UI de troca mais clara  
- [ ] Dividendos creditados no paper “ao vivo” (hoje forte no backtest)  
- [ ] Alertas quando score de um holding piora  

### IA / contexto
- [ ] Camada de IA (resumo de notícias, narrativa da tese, “por que essa ação?”)  
- [ ] Regime macro (Selic, IPCA) ajustando pesos setoriais  

### UX / produto
- [ ] Onboarding global na primeira visita  
- [ ] Explicar “Modo treino” em **todas** as páginas com o seletor (padrão do Teste no passado)  
- [ ] Testes automatizados (pytest) para scoring, portfolio, backtest  
- [ ] CI no GitHub (lint + testes)  
- [ ] Deploy (Streamlit Community Cloud / Docker)  

### Qualidade
- [ ] Tipagem e validação mais rígidas nos DataFrames  
- [ ] Tratar rate-limit yfinance com backoff/UX  
- [ ] Internacionalização (só se pedido)  

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

*Última atualização do handoff: 2026-08-07.*
