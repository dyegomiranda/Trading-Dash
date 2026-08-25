# TradingDash

App em **Streamlit** para estudar a tese **Quality Dividend** na bolsa brasileira (B3): ranking de ações, carteira de treino (paper money), projeção de renda e simulação histórica.

> Ferramenta de estudo. **Não é recomendação de investimento.**

**Repositório:** https://github.com/dyegomiranda/Trading-Dash

---

## O que o app faz

| Página | Função |
|--------|--------|
| **Início** | Visão geral: patrimônio de treino, 4 notas da tese e **notícias reais** com links |
| **Descubra ações** | Nota 0–100, pesos sugeridos e **gráfico histórico** de preço |
| **Minha carteira** | Capital editável, aplicar tese, alocar manualmente, projetar renda |
| **Teste no passado** | “E se eu tivesse seguido a tese desde 2022?” — com guia antes do 1º teste |
| **Guia do iniciante** | Dicionário, fontes de dados e a estratégia em português claro |
| **Configurações** | Modo treino, fonte B3 experimental e inclinação por juros |

### Modo treino vs Bolsa real

| | **Bolsa real (padrão)** | **Modo treino** |
|--|------------------------|-----------------|
| Nome / setor | Yahoo + cadastro B3 local | Cadastro B3 local (**não inventa setor**) |
| Preços e indicadores | Yahoo Finance | **Sintéticos — nunca para dinheiro real** |
| Quando usar | Análise / simulação com dados de mercado | Só aprender a interface |

> **Aviso de confiabilidade:** o app é MVP. Mesmo em Bolsa real, o Yahoo é gratuito e falível. Valide tickers, setores e números em RI/CVM/Status Invest antes de qualquer decisão. Cadastro de referência: `data/reference/b3_tickers.json` (atualizável com `scripts/refresh_b3_metadata.py`).

---

## Como rodar

```bash
git clone https://github.com/dyegomiranda/Trading-Dash.git
cd Trading-Dash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
```

Abra o endereço local (geralmente `http://localhost:8501`).

### Binários (sem instalar Python)

Na página [Releases](https://github.com/dyegomiranda/Trading-Dash/releases) (ou em **Actions → Binaries**, após um tag `v*` ou disparo manual):

| Sistema | Arquivo | Como usar |
|---------|---------|-----------|
| Linux | `TradingDash-x86_64.AppImage` | `chmod +x` e execute. Carteiras em `~/.local/share/TradingDash/` |
| Windows | `TradingDash-windows.zip` | Extraia e rode `TradingDash.exe`. Carteiras em `%APPDATA%\TradingDash\` |

Os dados da carteira **não saem do seu computador**.

**fish shell:** prefira `.venv/bin/streamlit run app.py`.  
Para ativar o venv no fish: `source .venv/bin/activate.fish`.

### Deploy no Streamlit Community Cloud (para testar sem instalar)

**Antes de publicar**, rode o pre-flight local (mesmo “contrato” que o Cloud executa:
`pip install -r requirements.txt` + `streamlit run app.py`, sem rede):

```bash
python deploy/preflight.py
# deve terminar com "TUDO OK — pronto para deploy."
```

Passos no painel:

1. Repo no GitHub: `https://github.com/dyegomiranda/Trading-Dash`  
2. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login com GitHub  
3. **New app** → selecione o repo → branch `main`  
4. **Main file path:** `app.py`  
5. **Secrets** (opcional): no painel **Settings → Secrets**, adicione
   `BRAPI_TOKEN=...` (dados B3) e/ou `XAI_API_KEY=...` (coach com IA).
   Tudo funciona sem elas; a fonte padrão é Yahoo.  
6. Deploy  

**O que esperar do free tier:** cache e carteiras paper (`data/cache`, `data/portfolio`)
são **ephemeral** — reiniciam a cada cold start/rebuild. A cobertura de dados
(cadastro B3) é versionada no git e **sobrevive** ao deploy. Se quiser persistência
real, é preciso um host com disco (ex.: render/fly.io + volume, ou Docker + bind mount).

---

## Uso rápido (iniciante)

1. **Início** — tour curto; a primeira visita já entra no **Modo treino**.  
2. **Descubra ações** — as 4 notas da tese e o porquê de cada nome.  
3. **Minha carteira** — ajuste o capital se quiser e clique em **Montar carteira com a tese**.  
4. **Renda esperada** — 3 cenários (sem inventar yield se a carteira estiver vazia).  
5. **Teste no passado** (opcional) — ensaio do motor com o retrato de hoje, não o balanço de 2022.

---

## Tese (resumo)

**Quality Dividend** — renda passiva com qualidade:

- empresas sólidas (lucro e caixa consistentes)  
- dividendos **sustentáveis** (não “high yield trap”)  
- carteira **base** (~70%) + **complemento** (~30%)  

### Regime macro (opcional)

O app pode reorientar os pesos sugeridos conforme o ciclo de juros reais (Selic − IPCA 12m),
usando dados públicos do **Banco Central (SGS)**:

- **Desligado** (padrão) — comportamento atual, sem inclinação setorial.
- **Automático** — classifica Selic real em *expansivo / cauteloso / restritivo* e aplica
  inclinação setorial correspondente (mais defensivas em juros altos; mais crescimento em
  juros baixos).
- **Manual** — escolha direta: juros altos, juros baixos ou neutro.

A inclinação é **transparente e reversível**: multiplica o peso de cada setor (range ±~15%),
renormaliza para somar 100% e respeita os tetos por ação/setor — nunca cria nem exclui
posições. Configure em **Regime macro** na barra lateral (vale na lista e em Montar carteira)
ou via `MACRO_OVERRIDE` no `.env` (`off` | `auto` | `expansionary` | `cautious` | `restrictive`).
A série usada é a **meta Selic (SGS 432)**, em % a.a.

---

## Estrutura (visão rápida)

```
app.py              # entrada + menu (logo acima dos links)
app_pages/          # telas do app
src/                # scoring, dados, carteira, backtest, UI
assets/             # logo e ícone
PROJECT.md          # handoff técnico completo (para devs / outras IAs)
```

Para arquitetura, bugs já resolvidos e **backlog do que falta**, veja **[PROJECT.md](./PROJECT.md)**.

---

## Confiabilidade da simulação (Fases A e B)

- **No rebalance:** preço = fechamento daquele dia; dividend yield = TTM dos proventos já pagos (sem olhar o futuro).
- **Custos ligados por padrão:** corretagem 15 bps, slippage 10 bps, ~25% do provento como JCP (15% na fonte), IR 15% no ganho de capital, atraso de 15 dias no crédito do dividendo.
- **Liquidez (ADV):** exclui papéis pouco negociados e limita o tamanho da ordem.
- **Monte Carlo:** reamostra **esta** curva (P10/P50/P90). Não é previsão do mercado.
- **Walk-forward:** parte o período em treino (~70%) e teste (~30%). Opcional: teste cego que recomeça no corte.
- **Splits/bonificação:** quantidade só muda se o preço do dia ainda for cru. O ensaio usa `close` (não `adj_close`) para não contar dividendo duas vezes. Subscrição não é exercida.
- **Balanços point-in-time:** JSON gerado dos DFP/ITR da CVM (2020–2024, `origin=cvm_dfp_itr`). Só contas (ROE/margem/dívida). Para atualizar:

```bash
.venv/bin/python scripts/download_cvm_data.py --years 2020-2025 --download
.venv/bin/python scripts/download_cvm_data.py --years 2020-2025 --build
```

A CVM não publica preço nem yield — o motor continua usando o pregão do dia.

---

## Limitações conhecidas

- Fontes gratuitas de cotação podem falhar ou atrasar. brapi.dev é experimental (quase sem ROE/dívida no plano grátis).
- A semente PIT **não** elimina look-ahead contábil. Só o parse CVM (`origin=cvm_dfp_itr`) cobre contas.
- Ferramenta educacional / paper trading. **Não é recomendação de investimento.**

---

## Licença

Ver arquivo [LICENSE](./LICENSE).
