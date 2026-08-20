"""Componentes HTML da UI (separados do CSS para imports estáveis)."""

from __future__ import annotations

import html
from collections.abc import Sequence

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
    """Caixa leve de orientação (não usa st.info pesado)."""
    with st.container(border=True):
        st.markdown(f"**{icon} {title}**")
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
    """Setores da base da tese, em português — o que o iniciante precisa ver."""
    with st.container(border=True):
        st.markdown("##### Base da tese (~70%)")
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

