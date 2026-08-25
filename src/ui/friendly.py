"""Textos, rótulos e componentes de UI em linguagem simples."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui.components import (
    apply_theme,
    render_brand,
    render_disclaimer_bar,
    render_guide_box,
)

# Nomes técnicos → nomes que um iniciante entende (sem jargão)
COLUMN_LABELS: dict[str, str] = {
    "ticker": "Código da ação",
    "name": "Nome da empresa",
    "sector": "Setor da empresa",
    "industry": "Ramo de atividade",
    "price": "Preço de hoje (R$)",
    "market_cap": "Tamanho da empresa",
    "bucket": "Papel na carteira",
    "rank": "Posição geral",
    "rank_filtered": "Posição",
    "score_total": "Nota do app (0–100)",
    "score_quality": "Nota de qualidade do negócio",
    "score_dividends": "Nota de dividendos",
    "score_financial_health": "Nota de saúde financeira",
    "score_valuation": "Nota de preço justo",
    "dividend_yield": "Quanto paga de dividendo ao ano (%)",
    "roe": "Lucro sobre o patrimônio",
    "roic": "Retorno sobre o capital investido",
    "roa": "Lucro sobre os ativos",
    "payout": "Parte do lucro paga em dividendos",
    "net_debt_ebitda": "Nível de endividamento",
    "debt_equity": "Dívida em relação ao patrimônio",
    "pe": "Preço em relação ao lucro",
    "pb": "Preço em relação ao patrimônio",
    "ev_ebitda": "Preço da empresa / geração de caixa",
    "fcf_yield": "Caixa livre / valor da empresa",
    "target_weight": "Fatia sugerida na carteira",
    "shares": "Quantidade de ações",
    "avg_price": "Preço médio de compra",
    "market_value": "Valor atual da posição",
    "cost": "Quanto você pagou",
    "pnl": "Lucro ou prejuízo (R$)",
    "pnl_pct": "Lucro ou prejuízo (%)",
    "weight": "Fatia na carteira",
    "annual_income": "Renda estimada por ano",
    "monthly_income": "Renda estimada por mês",
    "reject_reason": "Por que não passou no filtro",
    "side": "Compra ou venda",
    "amount": "Valor (R$)",
    "note": "Observação",
    "date": "Data",
    "equity": "Dinheiro total na conta",
    "cash": "Dinheiro livre no caixa",
    "n_positions": "Nº de empresas na carteira",
    "projected_annual_income": "Renda anual projetada",
    "projected_monthly_income": "Renda mensal projetada",
    "portfolio_equity_est": "Patrimônio estimado",
    "year": "Ano",
    "ts": "Quando",
    "severidade": "Gravidade",
    "codigo": "Código do alerta",
    "mensagem": "O que está acontecendo",
    "acao_sugerida": "O que você pode fazer",
}

# Períodos de gráfico de preço (rótulo amigável → dias aproximados; None = máximo)
PRICE_PERIODS: list[tuple[str, int | None]] = [
    ("1 mês", 30),
    ("3 meses", 90),
    ("6 meses", 180),
    ("1 ano", 365),
    ("2 anos", 730),
    ("5 anos", 1825),
    ("Máximo disponível", None),
]

BUCKET_LABELS = {
    "core": "Base (mais estável)",
    "satellite": "Complemento (um pouco mais arriscado)",
}

# Códigos de alerta (src/thesis/alerts.py) → o que o iniciante entende.
# Cobrem os códigos atuais; qualquer código novo aparece como está (dev a vê).
ALERT_CODE_LABELS: dict[str, str] = {
    "ok": "Tudo certo",
    "sem_dados": "Sem dados agora",
    "score_muito_baixo": "Nota muito baixa",
    "score_abaixo_minimo": "Nota abaixo do mínimo",
    "score_caindo": "Nota caindo",
    "score_subindo": "Nota subindo",
    "sem_dividendo": "Sem dividendo",
    "dy_muito_alto": "DY muito alto",
    "payout_alto": "Payout alto",
    "alavancagem_alta": "Endividamento alto",
    "roe_fraco": "ROE fraco",
    "fcf_negativo": "Caixa livre negativo",
    "dados_incompletos": "Dados incompletos",
}

# Gravidade do alerta → rótulo simples
SEVERITY_LABELS: dict[str, str] = {
    "info": "Informativo",
    "warning": "Atenção",
    "critical": "Crítico",
}

# Ação sugerida do alerta → verbo claro
ACTION_LABELS: dict[str, str] = {
    "monitorar": "Acompanhar",
    "reduzir": "Reduzir",
    "sair": "Sair",
}

GLOSSARY: list[tuple[str, str]] = [
    (
        "Modo treino",
        "Interruptor da barra. Ligado: o app usa números ilustrativos para você aprender. Desligado: busca a bolsa (Yahoo).",
    ),
    (
        "Bolsa real",
        "Preços e indicadores do Yahoo Finance. São de mercado, mas gratuitos — podem atrasar, faltar ou divergir da CVM.",
    ),
    (
        "brapi.dev",
        "Empresa que junta dados da B3. No plano grátis traz preço e dividendo, quase sem ROE nem dívida. Fica em Configurações.",
    ),
    (
        "Atualizar dados",
        "Apaga os números guardados (cache) e busca de novo. Use se a lista parecer antiga.",
    ),
    (
        "Inclinação por juros",
        "Em Configurações. Pode dar um pouco mais de peso a setores estáveis quando os juros estão altos. Não cria nem tira ações.",
    ),
    (
        "Ação",
        "Uma fatia de uma empresa. Quando você compra ações, vira sócio em miniatura.",
    ),
    (
        "Código da ação (ticker)",
        "Apelido da ação na bolsa. Ex.: ITUB4 (Itaú), WEGE3 (WEG), TAEE11 (Taesa).",
    ),
    (
        "Dividendo",
        "Parte do lucro que a empresa distribui aos acionistas. É a “renda” da ação.",
    ),
    (
        "Renda passiva",
        "Dinheiro que entra sem você precisar trabalhar todo dia — por exemplo, dividendos.",
    ),
    (
        "DY / renda por dividendo",
        "Quanto a ação paga de dividendo em um ano, em % do preço. Ex.: 6% em R$ 100 ≈ R$ 6/ano.",
    ),
    (
        "Nota geral (score)",
        "Nota de 0 a 100 que o app dá para a ação segundo a estratégia escolhida. Quanto maior, melhor encaixe.",
    ),
    (
        "Base da carteira (core)",
        "Empresas mais estáveis, pensadas para ficar por mais tempo e gerar renda com mais previsibilidade.",
    ),
    (
        "Complemento (satélite)",
        "Parte menor da carteira, um pouco mais flexível, que você pode revisar com mais frequência.",
    ),
    (
        "Carteira de treino (paper money)",
        "Dinheiro de mentira para praticar compras e vendas sem risco real.",
    ),
    (
        "Rebalancear",
        "Ajustar as quantidades para ficar próximo dos pesos sugeridos (comprar umas, vender outras).",
    ),
    (
        "Simulação no passado",
        "Pergunta: “e se eu tivesse seguido essas indicações desde tal data?”. Serve para estudar, não para garantir o futuro.",
    ),
    (
        "Patrimônio",
        "Dinheiro em caixa + valor das ações que você tem.",
    ),
    (
        "Crescimento médio ao ano (CAGR)",
        "Quanto seu dinheiro teria crescido, em média, por ano no período da simulação.",
    ),
    (
        "Maior queda (drawdown)",
        "A pior “descida” do patrimônio no período — útil para entender o estômago necessário.",
    ),
    (
        "Modo treino (Demo)",
        "Dados inventados mas realistas, para aprender o app sem internet e sem demora.",
    ),
    (
        "Dados da bolsa (Yahoo)",
        "Tenta buscar informações reais de empresas listadas no Brasil. Pode demorar na primeira vez.",
    ),
    (
        "Dinheiro total na conta",
        "Soma de tudo: o que está livre no caixa + o valor atual das ações. É o “quanto você tem” na conta de treino.",
    ),
    (
        "Dinheiro livre no caixa",
        "Parte ainda não aplicada em ações. Serve para comprar novas empresas.",
    ),
    (
        "Valor aplicado em ações",
        "Quanto está investido nas empresas da carteira, pelo preço de hoje (simulado).",
    ),
    (
        "Renda estimada (dividendos)",
        "Quanto a carteira poderia pagar por mês/ano se as empresas mantiverem o ritmo atual de dividendos. É estimativa, não garantia.",
    ),
    (
        "Crescimento dos dividendos",
        "Hipótese de que as empresas aumentam o que pagam a cada ano (ex.: 4% a.a.). Serve só para desenhar cenários.",
    ),
    (
        "Reinvestir dividendos",
        "Em vez de “gastar” a renda, o modelo assume que você compra mais ações com esse dinheiro — e a renda futura pode crescer.",
    ),
]


JOURNEY_STEPS: list[tuple[str, str]] = [
    ("Definir capital", "Quanto você quer treinar"),
    ("Escolher ações", "Ver sugestões e notas"),
    ("Montar carteira", "Aplicar ou comprar manualmente"),
    ("Ver renda e riscos", "Entender o que esperar"),
]


def portfolio_journey_state(
    *,
    has_capital: bool,
    has_positions: bool,
    viewed_income: bool = False,
) -> tuple[int, int]:
    """Retorna (passo_atual, concluído_até) para a barra de jornada."""
    if not has_capital:
        return 0, -1
    if not has_positions:
        return 2, 0  # capital ok; ainda montando (pular “escolher” se já está na carteira)
    if not viewed_income:
        return 3, 2
    return 3, 3



def setup_page(
    page_title: str,
    page_icon: str = ":material/savings:",
    layout: str = "wide",
) -> None:
    """Config + tema visual. Chamar no topo de cada página (depois de set_page_config se já setado)."""
    apply_theme()
    render_brand(sidebar=True)


def friendly_dataframe(df: pd.DataFrame, extra_map: dict[str, str] | None = None) -> pd.DataFrame:
    """Renomeia colunas e traduz valores de bucket para exibição."""
    if df is None or df.empty:
        return df
    out = df.copy()
    if "bucket" in out.columns:
        out["bucket"] = out["bucket"].map(lambda x: BUCKET_LABELS.get(str(x), str(x)))
    if "side" in out.columns:
        out["side"] = out["side"].map(
            lambda x: "Compra" if str(x) == "buy" else ("Venda" if str(x) == "sell" else x)
        )
    if "codigo" in out.columns:
        # Alertas de tese: código técnico → nome legível para iniciante
        out["codigo"] = out["codigo"].map(
            lambda x: ALERT_CODE_LABELS.get(str(x), str(x))
        )
    if "severidade" in out.columns:
        out["severidade"] = out["severidade"].map(
            lambda x: SEVERITY_LABELS.get(str(x), str(x))
        )
    if "acao_sugerida" in out.columns:
        out["acao_sugerida"] = out["acao_sugerida"].map(
            lambda x: ACTION_LABELS.get(str(x), str(x))
        )
    if "ticker" in out.columns:
        from src.data.reference import format_ticker_display

        def _fmt_ticker(x: object) -> str:
            s = str(x)
            if not s or s == "nan" or "(" in s:
                return s
            return format_ticker_display(s)

        out["ticker"] = out["ticker"].map(_fmt_ticker)
    labels = {**COLUMN_LABELS, **(extra_map or {})}
    rename = {c: labels[c] for c in out.columns if c in labels}
    return out.rename(columns=rename)


def render_sidebar_brand() -> None:
    apply_theme()
    render_brand(sidebar=True)


def render_disclaimer() -> None:
    render_disclaimer_bar()


def render_data_source_help() -> None:
    with st.expander("O que é “fonte de dados”?", icon=":material/help:"):
        st.markdown(
            """
**Modo treino (recomendado para começar)**  
Usa empresas e números de exemplo. É rápido, funciona offline e serve para aprender o fluxo.

**Dados da bolsa**  
Tenta puxar informações reais do mercado brasileiro. Pode demorar e, às vezes, vir incompleto  
(é gratuito e nem sempre perfeito).

Dica: pratique primeiro no **modo treino**. Depois, se quiser, mude para dados da bolsa.
"""
        )


def render_glossary_expander() -> None:
    with st.expander("Dicionário rápido (palavras que você vai ver por aqui)", icon=":material/menu_book:"):
        for term, meaning in GLOSSARY:
            st.markdown(f"**{term}** — {meaning}")


def render_step_guide(steps: list[str], title: str = "Como usar esta página") -> None:
    render_guide_box(title, steps)
