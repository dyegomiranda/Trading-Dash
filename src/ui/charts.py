"""Gráficos Plotly no estilo modern trading dashboard."""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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
    "margin": {"l": 10, "r": 10, "t": 36, "b": 10},
    "legend": {
        "orientation": "h",
        "yanchor": "bottom",
        "y": -0.22,
        "xanchor": "center",
        "x": 0.5,
        "bgcolor": "rgba(0,0,0,0)",
        "font": {"size": 11, "color": "#94A3B8"},
    },
}


def _base_layout(title: str | None = None, height: int = 320, **extra: Any) -> dict[str, Any]:
    """Monta um único dict de layout — sem kwargs duplicados no update_layout."""
    layout: dict[str, Any] = {**_LAYOUT, "height": height}
    if title:
        layout["title"] = {
            "text": title,
            "font": {
                "size": 14,
                "color": "#CBD5E1",
                "family": "Inter, system-ui, sans-serif",
            },
            "x": 0.02,
            "xanchor": "left",
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
    """Rosca moderna com valor no centro (estilo wallet)."""
    fig = go.Figure(
        data=[
            go.Pie(
                labels=list(labels),
                values=list(values),
                hole=0.72,
                sort=False,
                direction="clockwise",
                textinfo="percent",
                textposition="outside",
                textfont={"size": 11, "color": "#94A3B8"},
                marker={
                    "colors": PALETTE * 3,
                    "line": {"color": "#070B14", "width": 2},
                },
                hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
            )
        ]
    )
    annotations = []
    if center_value:
        annotations.append(
            {
                "text": (
                    f"<span style='font-size:12px;color:#94A3B8'>{center_title}</span>"
                    f"<br><span style='font-size:20px;font-weight:700;color:#F8FAFC'>{center_value}</span>"
                ),
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "align": "center",
            }
        )
    fig.update_layout(
        **_base_layout(
            title=title,
            height=height,
            showlegend=True,
            annotations=annotations,
        )
    )
    return fig


def sector_bars(
    sector_df: pd.DataFrame,
    *,
    title: str = "Por setor",
    height: int = 340,
) -> go.Figure:
    """Barras horizontais de alocação por setor."""
    df = sector_df.sort_values("value", ascending=True)
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
            textfont={"color": "#94A3B8", "size": 11},
            hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        **_base_layout(
            title=title,
            height=height,
            showlegend=False,
            margin={"l": 10, "r": 50, "t": 36, "b": 10},
            xaxis={
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.65)",
                "zeroline": False,
                "color": "#64748B",
                "title": "",
            },
            yaxis={"showgrid": False, "color": "#94A3B8", "title": ""},
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
    center_value: str = "",
    title: str = "Patrimônio investido",
) -> go.Figure:
    df = holdings.copy()
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep="last")]
    if df.empty:
        return donut_allocation(
            ["—"], [1], center_title="", center_value="—", title=title
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
            ["—"], [1], center_title="", center_value=center_value or "—", title=title
        )
    return donut_allocation(
        labels.tolist(),
        values.tolist(),
        center_title="Investido",
        center_value=center_value,
        title=title,
    )


def income_area(projection: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=projection["year"],
            y=projection["projected_annual_income"],
            mode="lines",
            line={"color": "#A78BFA", "width": 3, "shape": "spline"},
            fill="tozeroy",
            fillcolor="rgba(167, 139, 250, 0.18)",
            hovertemplate="Ano %{x}<br>R$ %{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        **_base_layout(
            title="Renda projetada",
            height=300,
            showlegend=False,
            margin={"l": 40, "r": 16, "t": 36, "b": 40},
            xaxis={
                "title": "Ano",
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "dtick": 1,
            },
            yaxis={
                "title": "",
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
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
    )
    fig.update_layout(
        **_base_layout(
            title=title,
            height=320,
            showlegend=True,
            bargap=0.25,
            margin={"l": 40, "r": 10, "t": 36, "b": 40},
            xaxis={"title": "", "color": "#64748B", "showgrid": False},
            yaxis={
                "title": "Nota",
                "color": "#64748B",
                "gridcolor": "rgba(36,48,68,0.55)",
                "range": [0, 100],
            },
        )
    )
    fig.update_traces(marker_line_width=0)
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
            margin={"l": 40, "r": 16, "t": 36, "b": 40},
            xaxis={
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "title": "",
            },
            yaxis={
                "showgrid": True,
                "gridcolor": "rgba(36,48,68,0.55)",
                "color": "#64748B",
                "title": "R$",
            },
        )
    )
    return fig


def sector_breakdown_from_holdings(
    holdings: pd.DataFrame,
    fundamentals: pd.DataFrame,
) -> pd.DataFrame:
    """Agrega valor de mercado por setor."""
    if holdings is None or holdings.empty:
        return pd.DataFrame(columns=["sector", "value", "pct"])
    fund = fundamentals.copy() if fundamentals is not None else pd.DataFrame()
    sector_map: dict[str, str] = {}
    if not fund.empty and "ticker" in fund.columns:
        for _, row in fund.iterrows():
            sector_map[str(row["ticker"])] = str(row.get("sector") or "Outros")
    rows = []
    for _, h in holdings.iterrows():
        t = str(h["ticker"])
        rows.append(
            {
                "sector": sector_map.get(t, "Outros"),
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
