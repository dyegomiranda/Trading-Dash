"""Componentes HTML da UI (separados do CSS para imports estáveis)."""

from __future__ import annotations

import html
import math
from collections.abc import Sequence
from typing import Any

import streamlit as st

from src.ui.theme import COLORS, apply_theme


def render_brand(sidebar: bool = True) -> None:
    apply_theme()
    mark = '<div class="td-brand-mark">TD</div>'
    text = (
        '<div class="td-brand-text">'
        "<strong>TradingDash</strong>"
        "<span>Renda · treino · clareza</span>"
        "</div>"
    )
    block = f'<div class="td-brand">{mark}{text}</div>'
    if sidebar:
        st.sidebar.markdown(block, unsafe_allow_html=True)
    else:
        st.markdown(block, unsafe_allow_html=True)


def render_hero(
    title: str,
    subtitle: str,
    kicker: str = "TradingDash",
    chips: Sequence[str] | None = None,
) -> None:
    chips = chips or []
    chips_html = "".join(
        f'<span class="td-chip">{html.escape(c)}</span>' for c in chips
    )
    st.markdown(
        f"""
<div class="td-hero">
  <div class="td-hero-kicker">{html.escape(kicker)}</div>
  <h1>{html.escape(title)}</h1>
  <p>{html.escape(subtitle)}</p>
  <div class="td-hero-meta">{chips_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_page_header(
    title: str,
    subtitle: str = "",
    badges: Sequence[tuple[str, str]] | None = None,
) -> None:
    """Renderiza o cabeçalho de página com suporte a badges integrados.

    badges: [(label, variant)], onde variant pode ser 'live', 'demo', 'pit', 'warn' ou 'default'.
    """
    sub = f"<span>{html.escape(subtitle)}</span>" if subtitle else ""
    badges_html = ""
    if badges:
        items = []
        for text, variant in badges:
            cls = f"td-badge td-badge-{variant}" if variant in ("live", "demo", "pit", "warn") else "td-badge"
            items.append(f'<span class="{cls}">{html.escape(text)}</span>')
        badges_html = f'<span class="td-header-badges">{"".join(items)}</span>'

    st.markdown(
        f"""
<div class="td-page-title">
  <h2>{html.escape(title)}{badges_html}</h2>
  {sub}
</div>
""",
        unsafe_allow_html=True,
    )


def chart_card_open() -> None:
    st.markdown('<div class="td-chart-card">', unsafe_allow_html=True)


def chart_card_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_section_label(text: str) -> None:
    st.markdown(
        f'<div class="td-section-label">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_feature_cards(
    cards: Sequence[tuple[str, str, str]],
) -> None:
    """cards: (icon_emoji_or_text, title, body)"""
    parts = ['<div class="td-feature-grid">']
    for icon, title, body in cards:
        parts.append(
            f"""
<div class="td-feature">
  <div class="td-feature-icon">{html.escape(icon)}</div>
  <h3>{html.escape(title)}</h3>
  <p>{html.escape(body)}</p>
</div>
"""
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_steps_card(title: str, steps: Sequence[str]) -> None:
    items = "".join(f"<li>{html.escape(s)}</li>" for s in steps)
    st.markdown(
        f"""
<div class="td-step-card">
  <div class="td-section-label" style="margin-top:0">{html.escape(title)}</div>
  <ol>{items}</ol>
</div>
""",
        unsafe_allow_html=True,
    )


def render_kpi_row(
    items: Sequence[tuple[str, str, str | None, str | None]],
) -> None:
    """items: (label, value, hint, hint_class up|down|neutral|None)"""
    parts = ['<div class="td-kpi-row">']
    for label, value, hint, hint_class in items:
        hint_html = ""
        if hint:
            cls = hint_class or "neutral"
            hint_html = f'<div class="hint {html.escape(cls)}">{html.escape(hint)}</div>'
        parts.append(
            f"""
<div class="td-kpi">
  <div class="label">{html.escape(label)}</div>
  <div class="value">{html.escape(value)}</div>
  {hint_html}
</div>
"""
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_guide_box(title: str, steps: Sequence[str]) -> None:
    items = "".join(f"<li>{html.escape(s)}</li>" for s in steps)
    st.markdown(
        f"""
<div class="td-guide">
  <div class="td-guide-title">{html.escape(title)}</div>
  <ol>{items}</ol>
</div>
""",
        unsafe_allow_html=True,
    )


def render_journey(
    steps: Sequence[tuple[str, str]],
    *,
    current: int = 0,
    completed_through: int = -1,
) -> None:
    """Barra de jornada guiada.

    steps: lista de (título, dica curta)
    current: índice do passo atual (0-based)
    completed_through: último índice concluído (inclusive); -1 = nenhum
    """
    parts = ['<div class="td-journey">']
    for i, (title, detail) in enumerate(steps):
        cls = "td-journey-step"
        if i <= completed_through:
            cls += " done"
        if i == current:
            cls += " current"
        status = "Feito" if i <= completed_through else ("Agora" if i == current else f"Passo {i + 1}")
        parts.append(
            f"""
<div class="{cls}">
  <div class="n">{html.escape(status)}</div>
  <div class="t">{html.escape(title)}</div>
  <div class="d">{html.escape(detail)}</div>
</div>
"""
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_explain_card(title: str, value: str, body: str) -> None:
    """Card com número + texto em português claro (ideal para iniciantes)."""
    st.markdown(
        f"""
<div class="td-explain-card">
  <h4>{html.escape(title)}</h4>
  <div class="big">{html.escape(value)}</div>
  <p>{html.escape(body)}</p>
</div>
""",
        unsafe_allow_html=True,
    )


def render_plain_help(title: str, body: str, *, icon: str = ":material/lightbulb:") -> None:
    """Guia colapsável e discreto de orientação para não poluir a tela com texto."""
    with st.expander(title, expanded=False, icon=icon):
        st.markdown(body)


def render_disclaimer_bar(
    text: str = (
        "Ferramenta de estudo e treino. Não é recomendação de compra ou venda. "
        "Investimentos envolvem risco de perda."
    ),
) -> None:
    st.markdown(
        f"""
<div class="td-disclaimer">
  <span class="icon">ⓘ</span>
  <div>{html.escape(text)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def plotly_layout(**extra):
    """Layout padrão dark para Plotly (FundPip / wallet feel)."""
    base = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text"], family="Inter, sans-serif", size=12),
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["muted"]),
        ),
        xaxis=dict(
            gridcolor="rgba(36,48,68,0.7)",
            zerolinecolor="rgba(36,48,68,0.7)",
            color=COLORS["muted"],
        ),
        yaxis=dict(
            gridcolor="rgba(36,48,68,0.7)",
            zerolinecolor="rgba(36,48,68,0.7)",
            color=COLORS["muted"],
        ),
        colorway=list(
            [
                COLORS["primary"],
                COLORS["cyan"],
                COLORS["green"],
                COLORS["pink"],
                "#FBBF24",
                COLORS["primary_2"],
            ]
        ),
    )
    base.update(extra)
    return base


def style_plotly_fig(fig):
    fig.update_layout(**plotly_layout(title_font=dict(size=15, color=COLORS["text"])))
    fig.update_traces(marker_line_width=0)
    return fig


def _fmt_pillar(val: float | None) -> str:
    if val is None:
        return "—"
    try:
        f = float(val)
    except (TypeError, ValueError):
        return "—"
    if f != f:  # NaN
        return "—"
    return f"{f:.0f}"


def render_thesis_pillars(
    quality: float | None,
    dividends: float | None,
    health: float | None,
    valuation: float | None,
    *,
    heading: str = "As 4 notas da tese",
) -> None:
    """Quatro notas médias da lista, em português claro."""
    st.markdown(f"##### {heading}")
    st.caption(
        "Média das empresas desta lista, de 0 a 100. "
        "**Traço (—)** = não tínhamos esse dado; o app não inventa nota."
    )
    items = (
        ("Qualidade", quality, "Lucro e consistência do negócio"),
        ("Dividendos", dividends, "Renda sustentável, não o maior yield"),
        ("Saúde", health, "Dívida e folga financeira"),
        ("Preço", valuation, "Se o preço está razoável"),
    )
    cols = st.columns(4)
    for col, (label, val, hint) in zip(cols, items):
        with col, st.container(border=True):
            st.caption(label)
            st.markdown(f"**{_fmt_pillar(val)}**")
            st.caption(hint)


def pillar_means(df) -> tuple[float | None, float | None, float | None, float | None]:
    """Média dos 4 pilares num DataFrame pontuado (None se a coluna estiver vazia)."""
    import pandas as pd

    def _mean(col: str) -> float | None:
        if df is None or getattr(df, "empty", True) or col not in df.columns:
            return None
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        return float(s.mean()) if not s.empty else None

    return (
        _mean("score_quality"),
        _mean("score_dividends"),
        _mean("score_financial_health"),
        _mean("score_valuation"),
    )


def render_core_sectors_card() -> None:
    """Setores da base da tese, em português — recolhível para manter a UI limpa."""
    with st.expander("Composição setorial da tese (~70% Base / ~30% Complemento)", expanded=False, icon=":material/pie_chart:"):
        st.markdown(
            """
A carteira **base** privilegia negócios mais previsíveis no Brasil:

- **Energia e saneamento** (utilities) — tarifas e caixa mais estáveis  
- **Bancos e seguros** — lucro recorrente, histórico de dividendo  
- **Telecom** — receita de assinatura  
- **Consumo básico** (alimentos, higiene) — demanda pouco cíclica  

O **complemento** (~30%) pode ter indústria, materiais, energia de commodity
e outros — com teto por ação e por setor. Isso não é uma lista BESST fechada;
é o recorte que o app usa para “renda com qualidade”.
"""
        )


def render_goal_milestones(
    current_monthly_income: float,
    starting_capital: float = 10_000.0,
    monthly_contribution: float = 500.0,
    avg_yield: float = 0.07,
) -> None:
    """Renderiza as 4 metas realistas de renda passiva com progresso e tempo estimado."""
    milestones = [
        ("🎯 Meta 1: Contas Básicas / Luz", 450.0, "Paga contas de luz, água e internet"),
        ("🛒 Meta 2: Supermercado Pago", 2000.0, "Cobre compras essenciais do mês"),
        ("💼 Meta 3: Bom Salário Passivo", 5000.0, "Equivale a uma renda profissional estável"),
        ("🏝️ Meta 4: Independência Financeira", 20000.0, "Liberdade total para viver de dividendos"),
    ]

    cards_html = []
    for title, target_monthly, desc in milestones:
        # Patrimônio necessário = Renda Anual / Yield
        target_equity = (target_monthly * 12.0) / max(avg_yield, 0.01)
        pct = min(1.0, current_monthly_income / target_monthly) if target_monthly > 0 else 0.0
        is_completed = current_monthly_income >= target_monthly
        is_active = not is_completed and (pct > 0 or target_monthly == 450.0)

        # Cálculo de tempo com juros compostos e reinvestimento de dividendos (Annuity Formula)
        if starting_capital >= target_equity:
            years_est = 0.0
        else:
            r_monthly = (1.0 + max(avg_yield, 0.01)) ** (1.0 / 12.0) - 1.0
            pmt = max(monthly_contribution, 0.0)
            pv = max(starting_capital, 0.0)
            fv = target_equity

            if pmt > 0 and r_monthly > 0:
                num = fv * r_monthly + pmt
                den = pv * r_monthly + pmt
                if den > 0 and num > den:
                    months_est = math.log(num / den) / math.log(1.0 + r_monthly)
                    years_est = round(months_est / 12.0, 1)
                else:
                    years_est = 0.0
            elif pv > 0 and r_monthly > 0:
                months_est = math.log(fv / pv) / math.log(1.0 + r_monthly)
                years_est = round(months_est / 12.0, 1)
            else:
                years_est = 0.0

        cls = "completed" if is_completed else ("active" if is_active else "")
        status_text = "✅ Conquistada!" if is_completed else f"Faltam ~{years_est} anos (com aportes)" if years_est > 0 else "Em andamento"

        target_m_fmt = f"{target_monthly:,.0f}".replace(",", ".")
        target_eq_fmt = f"{target_equity:,.0f}".replace(",", ".")
        cards_html.append(
            f"""
<div class="td-goal-card {cls}">
  <div class="td-goal-header">
    <span class="td-goal-title">{html.escape(title)}</span>
  </div>
  <div class="td-goal-target">R$ {target_m_fmt} <span style="font-size:0.75rem; font-weight:500; color:#94A3B8;">/ mês</span></div>
  <div style="font-size:0.78rem; color:#CBD5E1; margin-bottom:0.4rem;">{html.escape(desc)}</div>
  <div class="td-goal-prog-track">
    <div class="td-goal-prog-bar" style="width: {pct * 100:.1f}%;"></div>
  </div>
  <div class="td-goal-footer">
    <span>Progresso: <b>{pct * 100:.1f}%</b></span>
    <span>{status_text}</span>
  </div>
  <div style="font-size:0.72rem; color:#64748B; margin-top:0.3rem;">Patrimônio alvo: ~R$ {target_eq_fmt}</div>
</div>
"""
        )

    st.markdown(
        f"""
<div class="td-goal-grid">
  {''.join(cards_html)}
</div>
""",
        unsafe_allow_html=True,
    )


def render_news_feed_cards(news_df) -> None:
    """Renderiza notícias no estilo feed visual moderno com pílulas de sentimento."""
    if news_df is None or getattr(news_df, "empty", True):
        st.caption("Nenhuma notícia recente disponível no momento.")
        return

    items_html = []
    for _, row in news_df.iterrows():
        title = html.escape(str(row.get("title", "")))
        url = html.escape(str(row.get("url", "#")))
        source = html.escape(str(row.get("source", "B3 News")))
        published = html.escape(str(row.get("published", "—")))
        ticker = html.escape(str(row.get("ticker", "")))
        sentiment = str(row.get("sentiment", "neutral"))
        sentiment_label = html.escape(str(row.get("sentiment_label", "Notícia")))

        pill_cls = f"td-sentiment-pill {sentiment}"

        items_html.append(
            f"""
<a href="{url}" target="_blank" class="td-news-item">
  <div>
    <div class="td-news-title">{title}</div>
    <div class="td-news-meta">
      <b>{ticker}</b> · <span>{source}</span> · <span>{published}</span>
    </div>
  </div>
  <div>
    <span class="{pill_cls}">{sentiment_label}</span>
  </div>
</a>
"""
        )

    st.markdown(
        f"""
<div class="td-news-feed">
  {''.join(items_html)}
</div>
""",
        unsafe_allow_html=True,
    )


def render_stock_health_meters(row: Any) -> None:
    """Exibe 4 medidores visuais de saúde em português claro para iniciantes (sem jargões).

    Substitui fórmulas complexas (P/L, ROE, Payout, Dív/EBITDA) por diagnósticos visuais:
    1. Preço Justo
    2. Saúde Financeira
    3. Dividendos Seguros
    4. Qualidade do Negócio
    """
    if row is None:
        return

    def _get(key: str) -> Any:
        if isinstance(row, dict):
            return row.get(key)
        try:
            return row[key]
        except Exception:
            return getattr(row, key, None)

    def _float(val: Any) -> float | None:
        try:
            v = float(val)
            return v if v == v else None
        except (TypeError, ValueError):
            return None

    pe = _float(_get("pe"))
    debt = _float(_get("net_debt_ebitda"))
    fcf_pos = _get("fcf_positive")
    dy = _float(_get("dividend_yield"))
    payout = _float(_get("payout"))
    roe = _float(_get("roe"))
    score_val = _float(_get("score_valuation"))
    score_health = _float(_get("score_financial_health"))
    score_div = _float(_get("score_dividends"))
    score_qual = _float(_get("score_quality"))

    # 1. Preço Justo
    if pe is not None and pe > 0:
        if pe <= 10.0:
            p_status, p_class, p_title, p_desc = (
                "🟢",
                "good",
                "Preço Atrativo",
                f"Descontada (P/L {pe:.1f}x) — histórico favorável",
            )
        elif pe <= 18.0:
            p_status, p_class, p_title, p_desc = (
                "🟡",
                "warn",
                "Preço Justo",
                f"Na média (P/L {pe:.1f}x) — valor equilibrado",
            )
        else:
            p_status, p_class, p_title, p_desc = (
                "🟠",
                "alert",
                "Preço Esticado",
                f"Mais cara (P/L {pe:.1f}x) — exige cautela",
            )
    elif score_val is not None:
        if score_val >= 65:
            p_status, p_class, p_title, p_desc = (
                "🟢",
                "good",
                "Preço Convidativo",
                "Nota alta de preço justo",
            )
        elif score_val >= 45:
            p_status, p_class, p_title, p_desc = (
                "🟡",
                "warn",
                "Preço Neutro",
                "Preço dentro da faixa esperada",
            )
        else:
            p_status, p_class, p_title, p_desc = (
                "🟠",
                "alert",
                "Preço Exigente",
                "Preço acima da média da tese",
            )
    else:
        p_status, p_class, p_title, p_desc = (
            "⚪",
            "neutral",
            "Não Avaliado",
            "Sem histórico recente de lucro",
        )

    # 2. Saúde Financeira
    if debt is not None:
        if debt <= 0:
            h_status, h_class, h_title, h_desc = (
                "🟢",
                "good",
                "Caixa Líquido",
                "Empresa tem mais dinheiro que dívidas",
            )
        elif debt <= 2.2 and fcf_pos is not False:
            h_status, h_class, h_title, h_desc = (
                "🟢",
                "good",
                "Finanças Sólidas",
                f"Dívida controlada ({debt:.1f}x) e caixa saudável",
            )
        elif debt <= 3.5:
            h_status, h_class, h_title, h_desc = (
                "🟡",
                "warn",
                "Dívida Moderada",
                f"Endividamento médio ({debt:.1f}x) — requer atenção",
            )
        else:
            h_status, h_class, h_title, h_desc = (
                "🔴",
                "alert",
                "Dívida Elevada",
                f"Dívida pesada ({debt:.1f}x) — maior risco",
            )
    elif score_health is not None:
        if score_health >= 65:
            h_status, h_class, h_title, h_desc = (
                "🟢",
                "good",
                "Finanças Seguras",
                "Boa solvência e baixo risco",
            )
        elif score_health >= 45:
            h_status, h_class, h_title, h_desc = (
                "🟡",
                "warn",
                "Equilíbrio Médio",
                "Solvência aceitável na tese",
            )
        else:
            h_status, h_class, h_title, h_desc = (
                "🔴",
                "alert",
                "Atenção a Dívidas",
                "Estrutura financeira fragilizada",
            )
    else:
        h_status, h_class, h_title, h_desc = (
            "⚪",
            "neutral",
            "Não Avaliado",
            "Dados de dívida indisponíveis",
        )

    # 3. Dividendos Seguros
    if payout is not None and payout > 1.05:
        d_status, d_class, d_title, d_desc = (
            "🔴",
            "alert",
            "Risco de Corte",
            f"Paga mais do que lucra (Payout {payout*100:.0f}%)",
        )
    elif dy is not None:
        dy_pct = dy * 100
        if dy >= 0.06:
            d_status, d_class, d_title, d_desc = (
                "🟢",
                "good",
                "Renda Forte & Segura",
                f"Dividendo de {dy_pct:.1f}% ao ano sustentável",
            )
        elif dy >= 0.035:
            d_status, d_class, d_title, d_desc = (
                "🟢",
                "good",
                "Renda Estável",
                f"Pagamento regular ({dy_pct:.1f}% ao ano)",
            )
        elif dy > 0:
            d_status, d_class, d_title, d_desc = (
                "🟡",
                "warn",
                "Dividendo Baixo",
                f"Renda modesta ({dy_pct:.1f}% ao ano)",
            )
        else:
            d_status, d_class, d_title, d_desc = (
                "⚪",
                "neutral",
                "Sem Rendimento",
                "Não distribui dividendos relevantes",
            )
    elif score_div is not None:
        if score_div >= 65:
            d_status, d_class, d_title, d_desc = (
                "🟢",
                "good",
                "Bons Dividendos",
                "Consistência comprovada de proventos",
            )
        elif score_div >= 45:
            d_status, d_class, d_title, d_desc = (
                "🟡",
                "warn",
                "Renda Moderada",
                "Distribuição aceitável",
            )
        else:
            d_status, d_class, d_title, d_desc = (
                "⚪",
                "neutral",
                "Pouca Renda",
                "Foco não é dividendo",
            )
    else:
        d_status, d_class, d_title, d_desc = (
            "⚪",
            "neutral",
            "Não Avaliado",
            "Sem histórico de dividendos",
        )

    # 4. Qualidade do Negócio
    if roe is not None:
        roe_pct = roe * 100
        if roe >= 0.18:
            q_status, q_class, q_title, q_desc = (
                "🟢",
                "good",
                "Altamente Rentável",
                f"Excelente lucro s/ patrimônio ({roe_pct:.0f}% ROE)",
            )
        elif roe >= 0.11:
            q_status, q_class, q_title, q_desc = (
                "🟢",
                "good",
                "Negócio Saudável",
                f"Rentabilidade consistente ({roe_pct:.0f}% ROE)",
            )
        elif roe >= 0.05:
            q_status, q_class, q_title, q_desc = (
                "🟡",
                "warn",
                "Rentabilidade Média",
                f"Gera lucro moderado ({roe_pct:.0f}% ROE)",
            )
        else:
            q_status, q_class, q_title, q_desc = (
                "🟠",
                "alert",
                "Baixa Eficiência",
                f"Retorno fraco ({roe_pct:.0f}% ROE)",
            )
    elif score_qual is not None:
        if score_qual >= 65:
            q_status, q_class, q_title, q_desc = (
                "🟢",
                "good",
                "Alta Eficiência",
                "Modelo de negócio forte e consistente",
            )
        elif score_qual >= 45:
            q_status, q_class, q_title, q_desc = (
                "🟡",
                "warn",
                "Eficiência Média",
                "Negócio aceitável",
            )
        else:
            q_status, q_class, q_title, q_desc = (
                "🟠",
                "alert",
                "Negócio Frágil",
                "Margens ou rentabilidade fracas",
            )
    else:
        q_status, q_class, q_title, q_desc = (
            "⚪",
            "neutral",
            "Não Avaliado",
            "Dados de rentabilidade ausentes",
        )

    cards = [
        ("Preço Justo", p_status, p_class, p_title, p_desc),
        ("Saúde Financeira", h_status, h_class, h_title, h_desc),
        ("Dividendos Seguros", d_status, d_class, d_title, d_desc),
        ("Qualidade do Negócio", q_status, q_class, q_title, q_desc),
    ]

    cards_html = []
    for label, icon, css_cls, title, desc in cards:
        cards_html.append(f"""
<div class="td-health-card">
  <div class="td-health-label">{html.escape(label)}</div>
  <div class="td-health-status {css_cls}">{icon} {html.escape(title)}</div>
  <div class="td-health-desc">{html.escape(desc)}</div>
</div>
""")

    st.markdown(
        f"""
<div class="td-health-grid">
  {''.join(cards_html)}
</div>
""",
        unsafe_allow_html=True,
    )


def render_quality_checklist(ticker: str) -> None:
    """Três checagens CVM/cadastro. Não é nota 0–10 nem recomendação de compra."""
    from src.thesis.checks import build_quality_checks

    checks = build_quality_checks(ticker)
    st.markdown("**O que dá para conferir (CVM + cadastro)**")
    st.caption(
        "Não é grau de convicção nem ordem de compra. "
        "Item sem dado fica em aberto — não preenchemos com chute."
    )
    icon = {
        "ok": ":material/check_circle:",
        "warn": ":material/warning:",
        "unknown": ":material/help:",
    }
    for item in checks.items:
        st.markdown(f"{icon[item.status]} **{item.title}** — {item.detail}")
        st.caption(item.source)
    st.caption(
        f"{checks.n_ok} ok · {checks.n_known} com dado · "
        f"{len(checks.items) - checks.n_known} sem dado na base."
    )


