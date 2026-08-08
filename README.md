# TradingDash

App em **Streamlit** para estudar a tese **Quality Dividend** na bolsa brasileira (B3): ranking de ações, carteira de treino (paper money), projeção de renda e simulação histórica.

> Ferramenta de estudo. **Não é recomendação de investimento.**

**Repositório:** https://github.com/dyegomiranda/Trading-Dash

---

## O que o app faz

| Página | Função |
|--------|--------|
| **Início** | Visão geral: patrimônio de treino, radar da tese e **notícias reais** com links |
| **Descubra ações** | Nota 0–100, pesos sugeridos e **gráfico histórico** de preço |
| **Minha carteira** | Capital editável, aplicar tese, alocar manualmente, projetar renda |
| **Teste no passado** | “E se eu tivesse seguido a tese desde 2022?” — com guia antes do 1º teste |
| **Guia do iniciante** | Dicionário e explicação da estratégia em português claro |

### Modo treino vs Bolsa real

| | **Modo treino** | **Bolsa real** |
|--|-----------------|----------------|
| O que é | Mercado **simulado** (rápido, offline) | Preços/dividendos via **Yahoo Finance** (`.SA`) |
| Quando usar | Aprender o fluxo, primeira vez | Experimentar com histórico mais “de verdade” |
| Limitação | Não é a B3 real | Pode ser lento/incompleto; score fundamental do MVP ainda não é 100% histórico |

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

**fish shell:** prefira `.venv/bin/streamlit run app.py`.  
Para ativar o venv no fish: `source .venv/bin/activate.fish`.

### Deploy no Streamlit Community Cloud (para o amigo testar sem instalar)

1. Repo no GitHub: `https://github.com/dyegomiranda/Trading-Dash`  
2. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login com GitHub  
3. **New app** → selecione o repo → branch `main`  
4. **Main file path:** `app.py`  
5. Deploy  

O app usa `requirements.txt` na raiz. Cache e carteiras paper ficam no servidor (efêmeros no free tier).

---

## Uso rápido (iniciante)

1. **Início** — veja o overview e as notícias.  
2. **Descubra ações** — Modo treino → **Atualizar** → explore o ranking e o histórico.  
3. **Minha carteira → Operar**  
   - ajuste o **capital** se quiser  
   - **Aplicar sugestões da tese** (feedback com as ordens)  
   - ou aloque **manualmente** por ação  
4. **Teste no passado** — leia o guia na tela → Modo treino + amostra rápida → **Rodar simulação**.  
5. Dúvidas de vocabulário: **Guia do iniciante**.

---

## Tese (resumo)

**Quality Dividend** — renda passiva com qualidade:

- empresas sólidas (lucro e caixa consistentes)  
- dividendos **sustentáveis** (não “high yield trap”)  
- carteira **base** (~70%) + **complemento** (~30%)  

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

## Limitações do MVP

- Simulação usa preços/dividendos históricos, mas o **score fundamental** ainda não é point-in-time contábil completo.  
- Não modela corretagem, impostos nem slippage.  
- Fontes gratuitas podem falhar ou demorar.

---

## Licença

Ver arquivo [LICENSE](./LICENSE).
