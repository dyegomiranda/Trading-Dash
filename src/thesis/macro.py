"""Regime macro (Selic/IPCA) e inclinação setorial da tese.

Em ciclos de juros altos e reais, empresas defensivas e pagadoras de dividendo
tendem a ter múltiplos mais estáveis; em ciclos de juros baixos, o mercado
valoriza mais crescimento e cíclicos. Este módulo classifica o regime atual e
produz um vetor de inclinação por setor usado pelo ``recommend_weights``.

Fontes (atenção às unidades — cada série chega com a sua):
- Selic: BCB SGS série 432 — meta Copom em **% a.a.** (ex.: 14.75).
  Não usamos a série 11 (% ao dia).
- IPCA: BCB SGS série 433 — variação mensal PERCENTUAL (ex.: 0.33 = +0,33%
  no mês). Acumulamos os últimos **12 prints** para o IPCA 12m.

Tudo é **transparente e reversível**: a inclinação fica no range ±15% por
setor e renormaliza os pesos para somar 100% — não cria nem exclui posições.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime
from typing import Any
from urllib.request import Request, urlopen

import pandas as pd

from src.config import CACHE_DIR, get_settings as _get_settings
from src.utils import utcnow

# Limiar de Selic real (% a.a.) para considerar regime "juros altos".
DEFAULT_SELIC_REAL_HIGH = 4.0  # acima disso: tilitar para defensivas
DEFAULT_IPCA_YEAR_TARGET = 3.0  # meta do BCB / referência de inflação "normal"

# Inclinação por setor por regime. Valores > 1 favorecem o setor; < 1 reduzem.
# Key: nome do setor (como vem no cadastro de referência B3).
_TILT_DEFENSIVE = {
    # Utilities / estáveis
    "Utilities": 1.12,
    "Electric Utilities": 1.12,
    "Regulated Electric": 1.12,
    "Water Utilities": 1.10,
    # Financeiro (maior margem com taxa alta)
    "Financial Services": 1.06,
    "Financials": 1.06,
    "Banks": 1.06,
    "Insurance": 1.04,
    "Telecom": 1.05,
    "Communication Services": 1.05,
    # Consumo defensivo
    "Consumer Defensive": 1.04,
    "Consumer Staples": 1.04,
}
_TILT_GROWTH = {
    "Industrials": 0.94,
    "Basic Materials": 0.90,
    "Energy": 0.92,
    "Healthcare": 0.95,
    "Real Estate": 0.94,
    "Consumer Cyclical": 0.94,
    "Technology": 0.93,
}

# Estados possíveis do regime (exibição amigável na UI).
REGIME_NAMES = {
    "expansionary": "Expansivo (juros baixos)",
    "cautious": "Cauteloso (juros moderados)",
    "restrictive": "Restritivo (juros altos)",
}

_CACHE_TTL_HOURS = 6


def _cache_path(key: str):
    h = hashlib.sha1(key.encode()).hexdigest()[:24]
    return CACHE_DIR / f"macro_{h}.json"


def _read_cache(key: str, ttl_hours: int = _CACHE_TTL_HOURS):
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - payload.get("ts", 0) > ttl_hours * 3600:
            return None
        return payload.get("data")
    except Exception:
        return None


def _write_cache(key: str, data: Any) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(key).write_text(
        json.dumps({"ts": time.time(), "data": data}, default=str),
        encoding="utf-8",
    )


def _fetch_bcb_series(
    code: int,
    start: str,
    end: str,
    *,
    ttl_hours: int | None = None,
) -> pd.Series | None:
    """Baixa uma série do Banco Central (SGS) com cache em disco."""
    if ttl_hours is None:
        from src.data.ttl import ttl_for

        ttl_hours = ttl_for("macro")
    cache_key = f"sgs{code}:{start}:{end}"
    cached = _read_cache(cache_key, ttl_hours)
    if cached is not None:
        s = pd.Series(cached) if not isinstance(cached, float) else pd.Series([cached])
        s.index = pd.to_datetime(s.index) if not s.index.empty else s.index
        return s.sort_index()

    url = (
        "https://api.bcb.gov.br/dados/serie/bcdata.sgs."
        f"{code}/dados?formato=json&dataInicial={start}&dataFinal={end}"
    )
    try:
        req = Request(url, headers={"User-Agent": "TradingDash/0.1"})
        with urlopen(req, timeout=20) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if not rows:
        return None
    s = pd.Series(
        {pd.to_datetime(r["data"], dayfirst=True).normalize(): float(str(r["valor"]).replace(",", "."))
         for r in rows}
    ).sort_index()
    _write_cache(
        cache_key,
        {str(k.date()): float(v) for k, v in s.items()},
    )
    return s


def fetch_macro_state(
    *,
    as_of: str | datetime | None = None,
) -> dict[str, Any]:
    """Busca Selic e IPCA atuais do BCB.

    Returns
    -------
    dict com 'selic_aa' (% a.a.), 'ipca_12m' (% em 12m), 'real_rate'
    (% a.a. real ≈ selic - ipca12), 'available' (bool), 'as_of'.
    """
    as_of_ts = pd.Timestamp(as_of or utcnow()).normalize()
    start = (as_of_ts - pd.Timedelta(days=400)).strftime("%d/%m/%Y")
    end = as_of_ts.strftime("%d/%m/%Y")

    # 432 = meta Selic do Copom (% a.a.). Não usar SGS 11 (% ao dia).
    selic = _fetch_bcb_series(432, start, end)
    ipca = _fetch_bcb_series(433, start, end)

    out = {
        "selic_aa": None,
        "ipca_12m": None,
        "real_rate": None,
        "available": False,
        "as_of": as_of_ts.date().isoformat(),
        "error": None,
    }

    if selic is not None and not selic.empty:
        # SGS 432 já vem em % a.a. (ex.: 14.75). Recusa print fora de 0–40.
        raw = float(selic.iloc[-1])
        if 0.0 < raw <= 40.0:
            out["selic_aa"] = raw
    if ipca is not None and not ipca.empty:
        monthly = ipca.dropna().sort_index()
        twelve = monthly.tail(12)
        # SGS 433: variação mensal em % (0.33 = +0,33%). Só os últimos 12 prints.
        if len(twelve) >= 6:
            factor = (1 + twelve / 100.0).prod()
            out["ipca_12m"] = float((factor - 1) * 100.0)

    if out["selic_aa"] is not None and out["ipca_12m"] is not None:
        out["real_rate"] = float(
            (1 + out["selic_aa"] / 100.0) / (1 + out["ipca_12m"] / 100.0) - 1.0
        ) * 100.0
        out["available"] = True

    return out


def classify_regime(
    real_rate: float | None,
    ipca_12m: float | None = None,
    *,
    high_threshold: float = DEFAULT_SELIC_REAL_HIGH,
) -> str:
    """Classifica o regime em expansionary | cautious | restrictive.

    Base principal: **Selic real**. Se o juro real está acima do limiar,
    é restritivo; perto de zero/negativo, expansivo.
    """
    if real_rate is None:
        return "cautious"  # sem dados → postura neutra
    if real_rate >= high_threshold:
        return "restrictive"
    if real_rate <= 1.0:
        return "expansionary"
    return "cautious"


def sector_tilt(
    regime: str,
    *,
    defensive: dict[str, float] | None = None,
    growth: dict[str, float] | None = None,
) -> dict[str, float]:
    """Vetor de multiplicador por setor conforme regime.

    As tabelas ``_TILT_DEFENSIVE``/``_TILT_GROWTH`` descrevem a postura do
    regime restritivo (defensivas >1, crescimento <1). No regime expansivo
    invertemos: exponemos o inverso dos multiplicadores (defensivas <1,
    crescimento >1), mantendo simetria. ``cautious`` é neutro (todos 1.0).

    - restrictive → inclina para defensivas (utilities, financeiro, staples).
    - expansionary → inclina para crescimento (industrial, tech, cíclicos).
    """
    d = dict(defensive or _TILT_DEFENSIVE)
    g = dict(growth or _TILT_GROWTH)

    def _invert(map_: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for k, v in map_.items():
            if v <= 0:
                out[k] = 1.0
            else:
                out[k] = round(1.0 / v, 4)
        return out

    if regime == "restrictive":
        return {k: v for k, v in {**d, **g}.items()}
    if regime == "expansionary":
        return {k: v for k, v in {**_invert(d), **_invert(g)}.items()}
    # cautious: neutro, mas devolve estrutura completa para a UI não quebrar
    all_sectors = set(d) | set(g)
    return {k: 1.0 for k in all_sectors}


def apply_sector_tilt(
    weights: pd.DataFrame,
    tilt: dict[str, float],
    sector_col: str = "sector",
) -> pd.DataFrame:
    """Aplica a inclinação setorial a um DataFrame de pesos.

    Multiplica ``target_weight`` pelo multiplicador do setor e RE-NORMALIZA
    para somar 1.0. Nunca cria/remove linhas.
    """
    if weights is None or weights.empty or not tilt:
        return weights
    out = weights.copy()
    if sector_col not in out.columns or "target_weight" not in out.columns:
        return out

    sec = out[sector_col].fillna("Outros").astype(str)
    mult = sec.map(lambda s: float(tilt.get(s, 1.0)))
    out["target_weight"] = out["target_weight"] * mult
    total = float(out["target_weight"].sum())
    if total > 0:
        out["target_weight"] = out["target_weight"] / total
    return out


def sector_tilt_from_override(
    override: str,
    *,
    high_threshold: float = DEFAULT_SELIC_REAL_HIGH,
) -> tuple[str, dict[str, float], dict[str, Any]]:
    """API de conveniência usada pela UI/-pages.

    ``override``: "auto" (busca o BCB) | "expansionary" | "cautious" |
    "restrictive". Retorna (regime, tilt, info).
    """
    info: dict[str, Any] = {
        "mode": override,
        "source": "override",
        "available": True,
    }
    if override == "auto":
        st = fetch_macro_state()
        info.update(st)
        regime = classify_regime(st.get("real_rate"), st.get("ipca_12m"))
        info["regime"] = regime
        info["regime_label"] = REGIME_NAMES.get(regime, regime)
        return regime, sector_tilt(regime), info
    if override in ("expansionary", "cautious", "restrictive"):
        regime = override
        info["regime"] = regime
        info["regime_label"] = REGIME_NAMES.get(regime, regime)
        return regime, sector_tilt(regime), info
    # inválido → neutro
    info["regime"] = "cautious"
    info["regime_label"] = REGIME_NAMES["cautious"]
    info["source"] = "invalid-override"
    return "cautious", sector_tilt("cautious"), info


def macro_tilt_from_settings(settings: Any | None = None) -> dict[str, float] | None:
    """Resolve a inclinação macro a partir das settings do app.

    Retorna ``None`` quando desligado ("off"), para o chamador pular o tilt.
    Demais valores usam ``sector_tilt_from_override``.
    """
    settings = settings or _get_settings()
    override = str(getattr(settings, "macro_override", "off") or "off")
    return macro_tilt_from_override(override)


def macro_tilt_from_override(override: str | None) -> dict[str, float] | None:
    """Resolve a inclinação a partir de um valor de override (ex.: da UI).

    "off" / vazio → None (desligado). Demais valores → tilt do regime.
    """
    override = str(override or "off")
    if override == "off":
        return None
    _regime, tilt, _info = sector_tilt_from_override(override)
    return tilt


def macro_header_info(override: str) -> dict[str, str]:
    """Texto curto para a UI (card do regime), com fallback quando sem dados."""
    regime, _tilt, info = sector_tilt_from_override(override)
    label = info.get("regime_label") or REGIME_NAMES.get(regime, regime)
    if info.get("mode") == "auto" and info.get("source") == "override" and not info.get("available"):
        return {
            "label": "Regime macro: sem dados ao vivo",
            "detail": "Sem resposta do Banco Central. Usando postura neutra.",
            "regime": regime,
        }
    selic = info.get("selic_aa")
    ipca = info.get("ipca_12m")
    real = info.get("real_rate")
    detail_parts = []
    if selic is not None:
        detail_parts.append(f"Selic {selic:.2f}% a.a.")
    if ipca is not None:
        detail_parts.append(f"IPCA 12m {ipca:.2f}%")
    if real is not None:
        detail_parts.append(f"real {real:.2f}%")
    detail = " · ".join(detail_parts) if detail_parts else ""
    return {
        "label": f"Regime macro: {label}",
        "detail": detail,
        "regime": regime,
    }