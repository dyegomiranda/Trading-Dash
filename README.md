# TradingDash

Dashboard Streamlit para estudar a tese **Quality Dividend** na B3: ranking filtrado, carteira **paper money**, projeção de renda e **simulação histórica** (backtest) das indicações.

> Ferramenta de estudo. **Não é recomendação de investimento.**

## O que tem no MVP

| Módulo | Função |
|--------|--------|
| **Ranking** | Universo amplo B3 → score Quality Dividend → filtros → top N com pesos core/satélite |
| **Carteira** | Paper trading (dinheiro fictício), rebalance pelas recomendações, projeção de renda |
| **Simulação** | “E se eu tivesse seguido a tese desde a data X?” — curva de patrimônio, trades, dividendos |
| **Demo / Yahoo** | Dados sintéticos offline ou yfinance (tickers `.SA`) |

## Tese

**Quality Dividend** focada em renda passiva:

- Qualidade (ROE/ROIC, margens, FCF)
- Dividendos sustentáveis (DY preferencial ~4–12%, payout saudável)
- Saúde financeira (alavancagem controlada)
- Valuation razoável
- Core ~70% / satélite ~30%

## Setup

```bash
git clone https://github.com/dyegomiranda/Trading-Dash.git
cd Trading-Dash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

**fish shell:** use `.venv/bin/streamlit run app.py` (o `source .venv/bin/activate` é para bash/zsh; no fish use `source .venv/bin/activate.fish`).

Abra o endereço local (geralmente `http://localhost:8501`).

### Recursos principais

- **Início:** overview, radar da tese, headlines reais (Google News / Yahoo)
- **Descubra ações:** ranking + gráficos de histórico de preço
- **Minha carteira:** capital editável, aplicar tese, alocação manual por ação
- **Teste no passado:** simulação histórica
- **Guia do iniciante:** dicionário e tese em português claro

## Uso rápido (para iniciantes)

1. Abra **Descubra ações**, mantenha **Modo treino**, clique em **Ver lista de sugestões**.
2. Em **Minha carteira**, use **Montar carteira com as sugestões** (R$ 100.000 fictícios).
3. Veja **Quanto posso receber de renda?**.
4. Em **Teste no passado**, rode com modo treino + amostra rápida (2022 → hoje).
5. Dúvidas de vocabulário: **Guia do iniciante**.

## Estrutura

```
TradingDash/
  app.py                 # Entrada + navegação (Início, Descubra ações, …)
  app_pages/             # Páginas (st.navigation)
  assets/logo/           # TD_logo.png
  assets/icon/           # TD_icon.png
  src/
    ui/                  # tema, componentes, charts, wallet
    config.py
    data/providers.py
    data/news.py         # headlines da tese
    thesis/scoring.py
    portfolio/
    backtest/engine.py
  data/cache/
  data/portfolio/
```

## Limitações do MVP

- Backtest usa **preços/dividendos históricos**, mas o **score fundamental** é snapshot atual (ou demo fixo) — não contabilidade point-in-time completa.
- Sem custos de corretagem, taxes, slippage.
- Yahoo pode ser lento / rate-limit no universo amplo.

## Próximos passos naturais

- Fundamentals históricos point-in-time (CVM / provedor pago)
- Camada de IA para resumo de notícias e narrativa da tese
- Regime macro (Selic, IPCA) ajustando pesos setoriais
- Benchmark vs Ibovespa / IDIV na simulação
