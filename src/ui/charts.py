"""Gráficos Plotly no estilo modern trading dashboard."""

from __future__ import annotations

from typing import Any
from collections.abc import Sequence

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.data.reference import format_ticker_display, get_ticker_meta, translate_sector

PALETTE = [
    "#A78BFA",
    "#818CF8",
    "#38BDF8",
    "#22D3EE",
    "#34D399",
    "#A3E635",
    "#FBBF24",
    "#FB923C",
    "#F472B6",
    "#E879F9",
    "#2DD4BF",
    "#60A5FA",
]

_LAYOUT: dict[str, Any] = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#E8EDF7", "family": "Inter, system-ui, sans-serif", "size": 12},
    "margin": {"l": 55, "r": 20, "t": 55, "b": 45},
    "legend": {
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "xanchor": "right",
        "x": 1.0,
        "bgcolor": "rgba(0,0,0,0)",
        "font": {"size": 11, "color": "#94A3B8"},
    },
}


def _base_layout(title: str | None = None, height: int = 320, **extra: Any) -> dict[str, Any]:
    """Monta um único dict de layout com título à esquerda e legenda à direita no topo."""
    layout: dict[str, Any] = {**_LAYOUT, "height": height}
    if title:
        layout["title"] = {
            "text": title,
            "font": {
                "size": 13,
                "color": "#CBD5E1",
                "family": "Inter, system-ui, sans-serif",
            },
            "x": 0.01,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
        }
    layout.update(extra)
    return layout


def donut_allocation(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    center_title: str = "Total",
    center_value: str = "",
    title: str = "Alocação",
    height: int = 340,
) -> go.Figure:
    """Rosca equilibrada, sem sobreposição de rótulos e com fatias limpas."""
    raw = [
        (str(lab), float(val))
        for lab, val in zip(labels, values)
        if val is not None and float(val) > 0
    ]
    if not raw:
        raw = [("—", 1.0)]
    raw.sort(key=lambda kv: kv[1], reverse=True)
    pie_labels = [lab for lab, _ in raw]
    pie_values = [val for _, val in raw]

    def _slice_ticker(lab: str) -> str:
        s = str(lab).strip()
        if s == "—":
            return s
        if "(" in s:
            return s.split("(", 1)[0].strip() or s
        return s

    def _hover_name(lab: str) -> str:
        s = str(lab).strip()
        if s == "—" or "(" in s:
            return s
        return format_ticker_display(s)

    slice_labels = [_slice_ticker(lab) for lab in pie_labels]
    hover_labels = [_hover_name(lab) for lab in pie_labels]
    n_slices = max(len(slice_labels), 1)
    colors = PALETTE * (n_slices // len(PALETTE) + 2)

    fig = go.Figure(
        data=[
            go.Pie(
                labels=slice_labels,
                values=pie_values,
                hole=0.55,
                sort=False,
                direction="clockwise",
                domain={"x": [0.04, 0.96], "y": [0.04, 0.96]},
                textinfo="label+percent",
                textposition="auto",
                insidetextorientation="horizontal",
                texttemplate="%{label} %{percent:.0%}",
                textfont={"size": 11, "color": "#FFFFFF"},
                hovertext=hover_labels,
                hovertemplate="<b>%{hovertext}</b><br>%{percent:.1%}<br>R$ %{value:,.2f}<extra></extra>",
                marker={
                    "colors": colors,
                    "line": {"color": "#070B14", "width": 1.5},
                },
            )
        ]
    )
    annotations = []
    if center_value:
        font_main = 15 if height >= 320 else 13
        annotations.append(
            {
                "text": (
                    f"<span style='font-size:10px;color:#94A3B8'>{center_title}</span>"
                    f"<br><span style='font-size:{font_main}px;font-weight:700;color:#F8FAFC'>{center_value}</span>"
                ),
                "x": 0.5,
                "y": 0.5,
                "xref": "paper",
                "yref": "paper",
                "xanchor": "center",
                "yanchor": "middle",
                "showarrow": False,
                "align": "center",
            }
        )
    top_margin = 52 if title else 24
    fig.update_layout(
        **_base_layout(
            title=title,
            height=max(height, 260),
            showlegend=False,
            margin={"l": 24, "r": 24, "t": top_margin, "b": 24},
            annotations=annotations,
            uniformtext={"minsize": 9, "mode": "hide"},
        )
    )
    return fig


def sector_bars(
    sector_df: pd.DataFrame,
    *,
    title: str = "Por setor",
    height: int = 340,
) -> go.Figure:
    """Barras horizontais de alocação por setor com espaçamento garantido para nomes longos."""
    df = sector_df.sort_values("value", ascending=True)
    eff_height = max(height, len(df) * 36 + 65)
    fig = go.Figure(
        go.Bar(
            x=df["value"],
            y=df["sector"],
            orientation="h",
            marker={
                "color": df["value"],
                "colorscale": [
                    [0, "#312E81"],
                    [0.5, "#7C3AED"],
                    [1, "#38BDF8"],
                ],
                "line": {"width": 0},
            },
            text=[f"{float(p):.0%}" for p in df["pct"]],
            textposition="outside",
            cliponaxis=False,
            textfont={"color": "#CBD5E1", "size": 11},
            hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        **_base_layout(
            title=title,
            height=eff_height,
            showlegend=False,
            margin={"l": 135, "r": 55, "t": 52, "b": 25},
            xaxis={
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "zeroline": False,
                "color": "#64748B",
                "automargin": True,
                "title": "",
            },
            yaxis={
                "showgrid": False,
                "color": "#CBD5E1",
                "automargin": True,
                "title": "",
            },
        )
    )
    return fig


def _as_series(df: pd.DataFrame, col: str) -> pd.Series:
    """Extrai uma Series mesmo se o nome da coluna estiver duplicado."""
    if col not in df.columns:
        raise KeyError(col)
    block = df.loc[:, df.columns == col]
    if isinstance(block, pd.DataFrame):
        s = block.iloc[:, -1]
    else:
        s = block
    return s


def holdings_donut(
    holdings: pd.DataFrame,
    *,
    value_col: str = "market_value",
    label_col: str = "ticker",
    center_title: str | None = None,
    center_value: str = "",
    title: str = "Patrimônio investido",
    height: int = 340,
) -> go.Figure:
    df = holdings.copy()
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep="last")]
    resolved_center_title = center_title or ("Renda anual" if value_col == "annual_income" else "Investido")
    if df.empty:
        return donut_allocation(
            ["—"], [1], center_title="", center_value="—", title=title, height=height
        )
    # Se o rename criou market_value em cima de outra market_value, use a coluna pedida com segurança
    if value_col not in df.columns and "annual_income" in df.columns:
        value_col = "annual_income"
    if label_col not in df.columns:
        # fallback: primeira coluna
        label_col = str(df.columns[0])

    labels = _as_series(df, label_col).astype(str)
    values = pd.to_numeric(_as_series(df, value_col), errors="coerce").fillna(0.0)
    # remove zeros que quebram a rosca
    mask = values > 0
    labels = labels[mask]
    values = values[mask]
    if len(values) == 0:
        return donut_allocation(
            ["—"], [1], center_title="", center_value=center_value or "—", title=title, height=height
        )
    return donut_allocation(
        labels.tolist(),
        values.tolist(),
        center_title=resolved_center_title,
        center_value=center_value,
        title=title,
        height=height,
    )


def income_area(
    projection: pd.DataFrame,
    *,
    title: str = "Dividendos estimados por mês (dinheiro que “entra”)",
    show_no_contrib: bool = True,
    monthly: bool = True,
) -> go.Figure:
    """Renda de dividendos no tempo.

    Por padrão mostra **por mês** (mais intuitivo para iniciantes).
    Não confundir com o gráfico de patrimônio (capital acumulado).
    """
    fig = go.Figure()
    if projection is None or projection.empty:
        fig.update_layout(
            **_base_layout(title=title, height=320, showlegend=False),
            annotations=[
                {
                    "text": "Sem dados de projeção",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"color": "#94A3B8"},
                }
            ],
        )
        return fig

    y_col = "projected_monthly_income" if monthly else "projected_annual_income"
    y_col_no = (
        "projected_monthly_income_no_contrib"
        if monthly
        else "projected_annual_income_no_contrib"
    )
    unit = "mês" if monthly else "ano"
    has_compare = (
        show_no_contrib
        and y_col_no in projection.columns
        and projection[y_col_no].notna().any()
    )
    if has_compare:
        fig.add_trace(
            go.Scatter(
                x=projection["year"],
                y=projection[y_col_no],
                mode="lines",
                name="Sem novos aportes (só o que já tem)",
                line={"color": "#64748B", "width": 2.2, "dash": "dot", "shape": "spline"},
                hovertemplate=(
                    "Ano %{x}<br>Sem aportar mais: R$ %{y:,.0f}/"
                    + unit
                    + "<extra></extra>"
                ),
            )
        )
    fig.add_trace(
        go.Scatter(
            x=projection["year"],
            y=projection[y_col],
            mode="lines+markers",
            name="Com aportes mensais",
            line={"color": "#A78BFA", "width": 3.2, "shape": "spline"},
            marker={"size": 7, "color": "#C4B5FD"},
            fill="tozeroy",
            fillcolor="rgba(167, 139, 250, 0.16)",
            hovertemplate=(
                "Ano %{x}<br>Com aportes: R$ %{y:,.0f}/" + unit + "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        **_base_layout(
            title=title,
            height=360,
            showlegend=True,
            margin={"l": 55, "r": 20, "t": 55, "b": 45},
            xaxis={
                "title": {"text": "Anos a partir de agora", "standoff": 10},
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "automargin": True,
                "dtick": 1,
            },
            yaxis={
                "title": {"text": f"Dividendos por {unit} (R$)", "standoff": 10},
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "automargin": True,
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1.0,
                "bgcolor": "rgba(0,0,0,0)",
                "font": {"size": 11, "color": "#94A3B8"},
            },
        )
    )
    return fig


def income_scenarios_chart(
    combined: pd.DataFrame,
    *,
    title: str = "Renda esperada: P10 / P50 / P90 (dividendos por mês)",
) -> go.Figure:
    """Gráfico amigável com P10 (cauteloso) / P50 (base) / P90 (animado)."""
    fig = go.Figure()
    if combined is None or combined.empty:
        fig.update_layout(**_base_layout(title=title, height=360, showlegend=False))
        return fig

    colors = {
        "P10 · cauteloso": "#94A3B8",
        "P50 · base": "#A78BFA",
        "P90 · animado": "#38BDF8",
        "Cauteloso": "#94A3B8",
        "Base (mais provável no modelo)": "#A78BFA",
        "Animado": "#38BDF8",
    }
    for scenario, g in combined.groupby("scenario", sort=False):
        fig.add_trace(
            go.Scatter(
                x=g["year"],
                y=g["projected_monthly_income"],
                mode="lines+markers",
                name=str(scenario),
                line={
                    "color": colors.get(str(scenario), "#A78BFA"),
                    "width": 3 if ("P50" in str(scenario) or "Base" in str(scenario)) else 2.2,
                    "shape": "spline",
                },
                marker={"size": 6},
                hovertemplate="Ano %{x}<br>%{fullData.name}: R$ %{y:,.0f}/mês<extra></extra>",
            )
        )
    fig.update_layout(
        **_base_layout(
            title=title,
            height=380,
            showlegend=True,
            margin={"l": 55, "r": 20, "t": 55, "b": 45},
            xaxis={
                "title": {"text": "Anos a partir de agora", "standoff": 10},
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "automargin": True,
                "dtick": 1,
            },
            yaxis={
                "title": {"text": "Dividendos por mês (R$)", "standoff": 10},
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "automargin": True,
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1.0,
                "bgcolor": "rgba(0,0,0,0)",
                "font": {"size": 11, "color": "#94A3B8"},
            },
        )
    )
    return fig


def snowball_chart(
    with_reinvest: pd.DataFrame,
    without_reinvest: pd.DataFrame,
    *,
    title: str = "Bola de neve: reinvestir dividendos vs sacar",
) -> go.Figure:
    """Compara o capital no tempo reinvestindo os dividendos vs sacando-os."""
    fig = go.Figure()
    base = with_reinvest if with_reinvest is not None and not getattr(with_reinvest, "empty", True) else pd.DataFrame()
    other = without_reinvest if without_reinvest is not None and not getattr(without_reinvest, "empty", True) else pd.DataFrame()
    if base.empty:
        fig.update_layout(**_base_layout(title=title, height=340, showlegend=False))
        return fig

    if not other.empty:
        fig.add_trace(
            go.Scatter(
                x=other["year"],
                y=other["portfolio_equity_est"],
                mode="lines+markers",
                name="Sem reinvestir (sacar dividendos)",
                line={"color": "#94A3B8", "width": 2.4, "dash": "dot"},
                marker={"size": 6},
                hovertemplate="Ano %{x}<br>Sacando: R$ %{y:,.0f}<extra></extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=base["year"],
            y=base["portfolio_equity_est"],
            mode="lines+markers",
            name="Reinvestindo os dividendos",
            line={"color": "#34D399", "width": 3.0, "shape": "spline"},
            marker={"size": 7},
            fill="tonexty" if not other.empty else "tozeroy",
            fillcolor="rgba(52, 211, 153, 0.14)",
            hovertemplate="Ano %{x}<br>Reinvestindo: R$ %{y:,.0f}<extra></extra>",
        )
    )
    # anota o ganho do reinvestimento no último ano
    if not other.empty and len(base) == len(other):
        end_diff = float(base["portfolio_equity_est"].iloc[-1] - other["portfolio_equity_est"].iloc[-1])
        fig.add_annotation(
            x=base["year"].iloc[-1],
            y=base["portfolio_equity_est"].iloc[-1],
            text=f"+R$ {end_diff:,.0f} reinvestindo".replace(",", "."),
            showarrow=True,
            arrowhead=2,
            arrowcolor="#34D399",
            font={"color": "#34D399", "size": 12},
            ax=0,
            ay=-40,
        )
    fig.update_layout(
        **_base_layout(
            title=title,
            height=340,
            showlegend=True,
            margin={"l": 55, "r": 20, "t": 55, "b": 45},
            xaxis={
                "title": {"text": "Anos a partir de agora", "standoff": 10},
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "automargin": True,
                "dtick": 1,
            },
            yaxis={
                "title": {"text": "Capital na carteira (R$)", "standoff": 10},
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "automargin": True,
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1.0,
                "bgcolor": "rgba(0,0,0,0)",
                "font": {"size": 11, "color": "#94A3B8"},
            },
        )
    )
    return fig


def equity_growth_area(
    projection: pd.DataFrame,
    *,
    title: str = "Capital acumulado na carteira (seu dinheiro investido)",
) -> go.Figure:
    """Evolução do capital (não é a renda mensal — é o “bolo” que gera dividendos)."""
    fig = go.Figure()
    if projection is None or projection.empty or "portfolio_equity_est" not in projection.columns:
        fig.update_layout(**_base_layout(title=title, height=280, showlegend=False))
        return fig

    # Barras = visual bem diferente do gráfico de renda (linhas roxas)
    fig.add_trace(
        go.Bar(
            x=projection["year"],
            y=projection["portfolio_equity_est"],
            name="Com aportes",
            marker={"color": "rgba(56, 189, 248, 0.75)", "line": {"width": 0}},
            hovertemplate="Ano %{x}<br>Capital na carteira: R$ %{y:,.0f}<extra></extra>",
        )
    )
    has_no = "portfolio_equity_no_contrib" in projection.columns
    if has_no:
        fig.add_trace(
            go.Scatter(
                x=projection["year"],
                y=projection["portfolio_equity_no_contrib"],
                mode="lines+markers",
                name="Sem novos aportes",
                line={"color": "#FBBF24", "width": 2.4, "dash": "dash"},
                marker={"size": 6},
                hovertemplate="Ano %{x}<br>Só capital de hoje: R$ %{y:,.0f}<extra></extra>",
            )
        )
    fig.update_layout(
        **_base_layout(
            title=title,
            height=340,
            showlegend=True,
            bargap=0.25,
            margin={"l": 55, "r": 20, "t": 55, "b": 45},
            xaxis={
                "title": {"text": "Anos a partir de agora", "standoff": 10},
                "showgrid": False,
                "color": "#64748B",
                "automargin": True,
                "dtick": 1,
            },
            yaxis={
                "title": {"text": "Capital na carteira (R$)", "standoff": 10},
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "automargin": True,
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1.0,
                "bgcolor": "rgba(0,0,0,0)",
                "font": {"size": 11, "color": "#94A3B8"},
            },
        )
    )
    return fig


def score_bars(df: pd.DataFrame, *, title: str = "Notas") -> go.Figure:
    plot = df.head(12).copy()
    fig = px.bar(
        plot,
        x="ticker",
        y="score_total",
        color="bucket" if "bucket" in plot.columns else None,
        color_discrete_map={
            "core": "#A78BFA",
            "satellite": "#38BDF8",
            "Base (mais estável)": "#A78BFA",
            "Complemento (um pouco mais arriscado)": "#38BDF8",
            "Base": "#A78BFA",
            "Complemento": "#38BDF8",
        },
        text="score_total" if "score_total" in plot.columns else None,
    )
    fig.update_traces(
        texttemplate="%{text:.0f}",
        textposition="inside",
        insidetextanchor="middle",
        textfont={"color": "#FFFFFF", "size": 11, "family": "Inter, sans-serif"},
        marker_line_width=0,
    )
    fig.update_layout(
        **_base_layout(
            title=title,
            height=320,
            showlegend=True,
            bargap=0.25,
            margin={"l": 48, "r": 20, "t": 55, "b": 35},
            xaxis={"title": "", "color": "#94A3B8", "showgrid": False, "automargin": True},
            yaxis={
                "title": {"text": "Nota", "standoff": 8},
                "color": "#64748B",
                "gridcolor": "rgba(36,48,68,0.55)",
                "range": [0, 105],
                "automargin": True,
            },
            legend={
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1.0,
                "bgcolor": "rgba(0,0,0,0)",
                "font": {"size": 11, "color": "#94A3B8"},
            },
        )
    )
    return fig


def price_history_chart(
    history: pd.DataFrame,
    *,
    ticker: str,
    title: str | None = None,
) -> go.Figure:
    """Gráfico de preço histórico de uma ação."""
    df = history.copy()
    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            **_base_layout(title=title or ticker, height=280, showlegend=False),
            annotations=[
                {
                    "text": "Sem histórico disponível",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"color": "#94A3B8"},
                }
            ],
        )
        return fig

    if "date" not in df.columns:
        df = df.reset_index()
        if "Date" in df.columns:
            df = df.rename(columns={"Date": "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    price_col = "close" if "close" in df.columns else ("adj_close" if "adj_close" in df.columns else None)
    if price_col is None:
        # tenta primeira coluna numérica
        nums = [c for c in df.columns if c != "date" and pd.api.types.is_numeric_dtype(df[c])]
        price_col = nums[0] if nums else None
    if price_col is None:
        return price_history_chart(pd.DataFrame(), ticker=ticker, title=title)

    y = pd.to_numeric(df[price_col], errors="coerce")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=y,
            mode="lines",
            line={"color": "#A78BFA", "width": 2.4, "shape": "spline"},
            fill="tozeroy",
            fillcolor="rgba(167,139,250,0.14)",
            hovertemplate="%{x|%d/%m/%Y}<br>R$ %{y:.2f}<extra></extra>",
            name=ticker,
        )
    )
    fig.update_layout(
        **_base_layout(
            title=title or f"{ticker} · preço",
            height=300,
            showlegend=False,
            margin={"l": 55, "r": 20, "t": 48, "b": 35},
            xaxis={
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "automargin": True,
                "title": "",
            },
            yaxis={
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "automargin": True,
                "title": {"text": "R$", "standoff": 8},
            },
        )
    )
    return fig


def sector_breakdown_from_holdings(
    holdings: pd.DataFrame,
    fundamentals: pd.DataFrame,
) -> pd.DataFrame:
    """Agrega valor de mercado por setor com tradução e fallback garantido."""
    if holdings is None or holdings.empty:
        return pd.DataFrame(columns=["sector", "value", "pct"])
    fund = fundamentals.copy() if fundamentals is not None else pd.DataFrame()
    sector_map: dict[str, str] = {}
    if not fund.empty and "ticker" in fund.columns:
        for _, row in fund.iterrows():
            raw_sector = row.get("sector")
            if raw_sector and str(raw_sector).strip() and str(raw_sector).strip() != "Unknown":
                sector_map[str(row["ticker"])] = str(raw_sector).strip()
    rows = []
    for _, h in holdings.iterrows():
        t = str(h["ticker"])
        sec = sector_map.get(t)
        if not sec or sec == "Unknown":
            meta = get_ticker_meta(t)
            sec = meta.get("sector")
            if not sec or sec == "Unknown":
                sec = "Outros"
        sec_pt = translate_sector(sec)
        rows.append(
            {
                "sector": sec_pt,
                "value": float(h.get("market_value") or 0),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=["sector", "value", "pct"])
    grouped = out.groupby("sector", as_index=False)["value"].sum()
    total = grouped["value"].sum() or 1.0
    grouped["pct"] = grouped["value"] / total
    return grouped.sort_values("value", ascending=False)