"""Alertas e regras de saída simples da tese Quality Dividend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.config import Settings, get_settings
from src.thesis.scoring import _safe, _unwrap


@dataclass
class HoldingAlert:
    ticker: str
    severity: str  # info | warning | critical
    code: str
    message: str
    action: str  # monitorar | reduzir | sair

    def as_dict(self) -> dict[str, str]:
        return {
            "ticker": self.ticker,
            "severidade": self.severity,
            "codigo": self.code,
            "mensagem": self.message,
            "acao_sugerida": self.action,
        }


def _row_val(row: pd.Series, key: str, default: Any = None) -> Any:
    if key not in row.index:
        return default
    return _unwrap(row[key])


def evaluate_holding(
    ticker: str,
    row: pd.Series | None,
    *,
    settings: Settings | None = None,
) -> list[HoldingAlert]:
    """Avalia um ativo da carteira contra regras simples da tese."""
    settings = settings or get_settings()
    t = str(ticker).upper()
    alerts: list[HoldingAlert] = []

    if row is None:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="warning",
                code="sem_dados",
                message="Não há dados de score/fundamentals para este ticker agora.",
                action="monitorar",
            )
        )
        return alerts

    score = _safe(_row_val(row, "score_total"), None)
    dy = _safe(_row_val(row, "dividend_yield"), None)
    payout = _safe(_row_val(row, "payout"), None)
    debt = _safe(_row_val(row, "net_debt_ebitda"), None)
    roe = _safe(_row_val(row, "roe"), None)
    fcf_pos = _row_val(row, "fcf_positive")
    bucket = str(_row_val(row, "bucket") or "")

    min_score = settings.rebalance_min_score

    if score is not None and score < min_score - 15:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="critical",
                code="score_muito_baixo",
                message=f"Nota geral {score:.0f} bem abaixo do mínimo da tese ({min_score:.0f}).",
                action="sair",
            )
        )
    elif score is not None and score < min_score:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="warning",
                code="score_abaixo_minimo",
                message=f"Nota geral {score:.0f} abaixo do mínimo da tese ({min_score:.0f}).",
                action="reduzir",
            )
        )

    if dy is not None and dy <= 0:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="critical",
                code="sem_dividendo",
                message="Dividend yield zerado ou indisponível — fere o foco de renda.",
                action="sair",
            )
        )
    elif dy is not None and dy > settings.preferred_dy_max + 0.04:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="warning",
                code="dy_muito_alto",
                message=(
                    f"DY {dy:.1%} muito alto (acima de ~{settings.preferred_dy_max:.0%}). "
                    "Pode ser armadilha de yield."
                ),
                action="monitorar",
            )
        )

    if payout is not None and payout > settings.max_payout:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="warning",
                code="payout_alto",
                message=f"Payout {payout:.0%} acima do limite saudável ({settings.max_payout:.0%}).",
                action="reduzir",
            )
        )

    if debt is not None and debt > settings.max_net_debt_ebitda:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="warning",
                code="alavancagem_alta",
                message=(
                    f"Dívida líquida/EBITDA {debt:.1f}x acima do teto "
                    f"({settings.max_net_debt_ebitda:.1f}x)."
                ),
                action="reduzir",
            )
        )

    if roe is not None and roe < settings.min_roe * 0.5:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="warning",
                code="roe_fraco",
                message=f"ROE {roe:.1%} bem fraco para a tese de qualidade.",
                action="monitorar",
            )
        )

    if fcf_pos is False:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="warning",
                code="fcf_negativo",
                message="Free cash flow negativo — dividendo pode não ser sustentável.",
                action="monitorar",
            )
        )

    if bucket and bucket not in ("core", "satellite"):
        pass

    if not alerts:
        alerts.append(
            HoldingAlert(
                ticker=t,
                severity="info",
                code="ok",
                message="Dentro das regras atuais da tese (nada crítico).",
                action="monitorar",
            )
        )

    return alerts


def evaluate_portfolio(
    tickers: list[str],
    scored: pd.DataFrame,
    *,
    settings: Settings | None = None,
) -> pd.DataFrame:
    """Gera tabela de alertas para todos os holdings."""
    settings = settings or get_settings()
    if scored is None or scored.empty:
        scored = pd.DataFrame()
    by_ticker: dict[str, pd.Series] = {}
    if not scored.empty and "ticker" in scored.columns:
        tmp = scored.copy()
        if tmp.columns.duplicated().any():
            tmp = tmp.loc[:, ~tmp.columns.duplicated(keep="last")]
        for _, row in tmp.iterrows():
            by_ticker[str(row["ticker"]).upper()] = row

    rows: list[dict[str, str]] = []
    for t in tickers:
        key = str(t).upper()
        for alert in evaluate_holding(key, by_ticker.get(key), settings=settings):
            # não poluir com "ok" se houver muitos ativos — mantém ok só se for o único tipo
            rows.append(alert.as_dict())

    if not rows:
        return pd.DataFrame(
            columns=["ticker", "severidade", "codigo", "mensagem", "acao_sugerida"]
        )

    df = pd.DataFrame(rows)
    # ordena: critical > warning > info
    order = {"critical": 0, "warning": 1, "info": 2}
    df["_ord"] = df["severidade"].map(order).fillna(9)
    df = df.sort_values(["_ord", "ticker"]).drop(columns=["_ord"])
    return df.reset_index(drop=True)


def exit_rules_summary(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return f"""
### Regras de saída / atenção (MVP)

| Situação | Ação sugerida |
|----------|----------------|
| Nota **&lt; {settings.rebalance_min_score - 15:.0f}** | **Sair** (deterioração forte) |
| Nota **&lt; {settings.rebalance_min_score:.0f}** | **Reduzir** / revisar |
| Sem dividendo (DY ≤ 0) | **Sair** |
| DY muito alto (&gt; ~{settings.preferred_dy_max + 0.04:.0%}) | Monitorar (possível high-yield trap) |
| Payout &gt; {settings.max_payout:.0%} | Reduzir |
| Dívida/EBITDA &gt; {settings.max_net_debt_ebitda:.1f}x | Reduzir |
| FCF negativo | Monitorar sustentabilidade do dividendo |

Estas regras são **educacionais** e automáticas a partir do snapshot atual — não disparam ordens sozinhas.
"""
