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

# Nomes técnicos → nomes que um iniciante entende
COLUMN_LABELS: dict[str, str] = {
    "ticker": "Código da ação",
    "name": "Nome da empresa",
    "sector": "Setor",
    "industry": "Ramo",
    "price": "Preço (R$)",
    "market_cap": "Tamanho da empresa",
    "bucket": "Tipo na carteira",
    "rank": "Posição geral",
    "rank_filtered": "Posição",
    "score_total": "Nota geral (0–100)",
    "score_quality": "Nota de qualidade",
    "score_dividends": "Nota de dividendos",
    "score_financial_health": "Nota de saúde financeira",
    "score_valuation": "Nota de preço justo",
    "dividend_yield": "Renda por dividendo (ao ano)",
    "roe": "Lucratividade (ROE)",
    "roic": "Retorno sobre o capital (ROIC)",
    "roa": "Retorno sobre ativos (ROA)",
    "payout": "Parte do lucro paga em dividendos",
    "net_debt_ebitda": "Nível de endividamento",
    "debt_equity": "Dívida / patrimônio",
    "pe": "Preço / lucro (P/L)",
    "pb": "Preço / valor patrimonial (P/VP)",
    "ev_ebitda": "Preço da empresa / geração de caixa",
    "fcf_yield": "Caixa livre / valor da empresa",
    "target_weight": "Peso sugerido na carteira",
    "shares": "Quantidade de ações",
    "avg_price": "Preço médio de compra",
    "market_value": "Valor atual",
    "cost": "Quanto você pagou",
    "pnl": "Lucro ou prejuízo",
    "pnl_pct": "Lucro ou prejuízo (%)",
    "weight": "Peso na carteira",
    "annual_income": "Renda estimada por ano",
    "monthly_income": "Renda estimada por mês",
    "reject_reason": "Por que não passou no filtro",
    "side": "Compra ou venda",
    "amount": "Valor (R$)",
    "note": "Observação",
    "date": "Data",
    "equity": "Patrimônio",
    "cash": "Dinheiro em caixa",
    "n_positions": "Nº de empresas na carteira",
    "projected_annual_income": "Renda anual projetada",
    "projected_monthly_income": "Renda mensal projetada",
    "portfolio_equity_est": "Patrimônio estimado",
    "year": "Ano",
    "ts": "Quando",
}

BUCKET_LABELS = {
    "core": "Base (mais estável)",
    "satellite": "Complemento (um pouco mais arriscado)",
}

GLOSSARY: list[tuple[str, str]] = [
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
]


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
