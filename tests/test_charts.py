"""Rosca sem rótulo sobreposto e médias dos 4 pilares."""

from __future__ import annotations

import pandas as pd

from src.ui.charts import donut_allocation
from src.ui.components import pillar_means


def test_donut_hover_uses_full_name():
    fig = donut_allocation(["LREN3"], [100.0])
    hover = list(fig.data[0].hovertext)
    assert hover
    assert "LREN3" in str(hover[0])
    assert "Renner" in str(hover[0])


def test_donut_labels_on_slices_with_percent():
    fig = donut_allocation(["ITUB4", "WEGE3", "TAEE11"], [40.0, 35.0, 25.0])
    pie = fig.data[0]
    assert pie.textinfo == "label+percent"
    assert pie.textposition in ("outside", "auto")
    assert "ITUB4" in list(pie.labels)
    assert fig.layout.showlegend is False
    center_xs = [a.x for a in (fig.layout.annotations or [])]
    assert not center_xs or all(abs(float(x) - 0.5) < 1e-6 for x in center_xs)


def test_donut_keeps_all_slices():
    labels = [f"T{i}" for i in range(12)]
    values = [20.0] + [1.0] * 11
    fig = donut_allocation(labels, values)
    names = list(fig.data[0].labels)
    assert "Outros" not in names
    assert len(names) == 12
    hover = list(fig.data[0].hovertext)
    assert len(hover) == 12


def test_pillar_means_none_when_missing():
    empty = pd.DataFrame({"ticker": ["A"]})
    assert pillar_means(empty) == (None, None, None, None)
    df = pd.DataFrame(
        {
            "score_quality": [80.0, 60.0],
            "score_dividends": [70.0, None],
            "score_financial_health": [None, None],
            "score_valuation": [50.0, 50.0],
        }
    )
    q, d, h, v = pillar_means(df)
    assert q == 70.0
    assert d == 70.0
    assert h is None
    assert v == 50.0


def test_chart_spacing_and_legend_alignment():
    from src.ui.charts import sector_bars, score_bars, income_area, price_history_chart

    # 1. sector_bars
    s_df = pd.DataFrame({"sector": ["Utilidade Pública", "Financeiro"], "value": [1000.0, 2000.0], "pct": [0.33, 0.67]})
    s_fig = sector_bars(s_df)
    assert s_fig.layout.margin.l >= 120
    assert s_fig.layout.yaxis.automargin is True

    # 2. score_bars
    sc_df = pd.DataFrame({"ticker": ["PETR4", "VALE3"], "score_total": [85.0, 78.0], "bucket": ["core", "core"]})
    sc_fig = score_bars(sc_df)
    assert sc_fig.layout.legend.y >= 1.0
    assert sc_fig.layout.legend.x == 1.0
    assert sc_fig.data[0].textposition == "inside"

    # 3. income_area
    inc_df = pd.DataFrame({"year": [1, 2, 3], "projected_monthly_income": [100.0, 200.0, 300.0]})
    inc_fig = income_area(inc_df)
    assert inc_fig.layout.legend.y >= 1.0
    assert inc_fig.layout.legend.x == 1.0
    assert inc_fig.layout.xaxis.title.standoff >= 10

    # 4. price_history_chart
    p_df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "close": [30.0, 31.0]})
    p_fig = price_history_chart(p_df, ticker="PETR4")
    assert p_fig.layout.yaxis.automargin is True
    assert p_fig.layout.margin.t >= 45

