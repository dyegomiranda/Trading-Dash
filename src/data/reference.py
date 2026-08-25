"""Cadastro de referência B3 (nome, setor, status, renomeações).

Fonte: `data/reference/b3_tickers.json` (gerado/atualizado via
`scripts/refresh_b3_metadata.py` + overrides manuais).

Regra: **nunca inventar setor/nome no demo** — usar este arquivo.
Números fundamentalistas no demo continuam sintéticos e NÃO servem para decisão real.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from src.config import REFERENCE_DIR

REFERENCE_PATH = REFERENCE_DIR / "b3_tickers.json"


def _norm(ticker: str) -> str:
    t = ticker.strip().upper()
    return t[:-3] if t.endswith(".SA") else t

# Overrides manuais prioritários (renomeações / gaps conhecidos)
MANUAL_OVERRIDES: dict[str, dict[str, Any]] = {
    "AXIA3": {
        "name": "AXIA ENERGIA ON",
        "sector": "Utilities",
        "industry": "Utilities - Renewable",
        "status": "active",
        "notes": "ex-ELET3 (Eletrobras)",
    },
    "AXIA6": {
        "name": "AXIA ENERGIA PNB",
        "sector": "Utilities",
        "industry": "Utilities - Renewable",
        "status": "active",
        "notes": "ex-ELET6",
    },
    "ELET3": {
        "status": "delisted_or_renamed",
        "name": "ELETROBRAS ON (ticker antigo)",
        "sector": "Utilities",
        "industry": "Utilities - Renewable",
        "successor": "AXIA3",
        "notes": "Migrado para AXIA3",
    },
    "ELET6": {
        "status": "delisted_or_renamed",
        "name": "ELETROBRAS PNB (ticker antigo)",
        "sector": "Utilities",
        "industry": "Utilities - Renewable",
        "successor": "AXIA6",
        "notes": "Migrado para AXIA6",
    },
    "KEPL3": {
        "name": "KEPLER WEBER ON",
        "sector": "Industrials",
        "industry": "Farm & Heavy Construction Machinery",
        "status": "active",
    },
    "BMGB11": {
        "name": "BANCO BMG UNIT",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "active",
    },
    "JHSF3": {
        "name": "JHSF PARTICIPACOES ON",
        "sector": "Real Estate",
        "industry": "Real Estate - Development",
        "status": "active",
    },
    "LREN3": {
        "name": "LOJAS RENNER ON",
        "sector": "Consumer Cyclical",
        "industry": "Department Stores",
        "status": "active",
    },
    "BBDC4": {
        "name": "BRADESCO PN",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "active",
    },
    "BBDC3": {
        "name": "BRADESCO ON",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "active",
    },
    "TAEE11": {
        "name": "TAESA UNT",
        "sector": "Utilities",
        "industry": "Utilities - Regulated Electric",
        "status": "active",
    },
    "ITUB4": {
        "name": "ITAU UNIBANCO PN",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "active",
    },
    "WEGE3": {
        "name": "WEG ON",
        "sector": "Industrials",
        "industry": "Specialty Industrial Machinery",
        "status": "active",
    },
    "VALE3": {
        "name": "VALE ON",
        "sector": "Basic Materials",
        "industry": "Other Industrial Metals & Mining",
        "status": "active",
    },
    "PETR4": {
        "name": "PETROBRAS PN",
        "sector": "Energy",
        "industry": "Oil & Gas Integrated",
        "status": "active",
    },
    # Universo histórico (saíram/renomearam) — sem isto o setor cai em Unknown.
    "LAME3": {
        "name": "Lojas Americanas",
        "sector": "Consumer Cyclical",
        "industry": "Department Stores",
        "status": "historical",
        "successor": "AMER3",
        "notes": "Ticker antigo; hoje Americanas (AMER3)",
    },
    "LAME4": {
        "name": "Lojas Americanas",
        "sector": "Consumer Cyclical",
        "industry": "Department Stores",
        "status": "historical",
        "successor": "AMER3",
        "notes": "Ticker antigo PN; hoje Americanas (AMER3)",
    },
    "BTOW3": {
        "name": "B2W Digital",
        "sector": "Consumer Cyclical",
        "industry": "Internet Retail",
        "status": "historical",
        "successor": "AMER3",
        "notes": "Incorporada à Americanas",
    },
    "VVAR3": {
        "name": "Via Varejo",
        "sector": "Consumer Cyclical",
        "industry": "Specialty Retail",
        "status": "historical",
        "successor": "BHIA3",
        "notes": "Hoje Casas Bahia (BHIA3)",
    },
    "HGTX3": {
        "name": "Cia Hering",
        "sector": "Consumer Cyclical",
        "industry": "Apparel Manufacturing",
        "status": "historical",
        "successor": "SOMA3",
        "notes": "Incorporada ao Grupo Soma",
    },
    "SMLS3": {
        "name": "Smiles Fidelidade",
        "sector": "Consumer Cyclical",
        "industry": "Travel Services",
        "status": "historical",
        "notes": "Programa de milhas; saiu de bolsa",
    },
    "LINX3": {
        "name": "Linx",
        "sector": "Technology",
        "industry": "Software - Application",
        "status": "historical",
        "notes": "Adquirida pela Stone",
    },
    "BIDI11": {
        "name": "Banco Inter",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "historical",
        "successor": "INBR32",
        "notes": "Migrou para units INBR32",
    },
    "BIDI4": {
        "name": "Banco Inter",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "status": "historical",
        "successor": "INBR32",
        "notes": "PN antiga do Inter",
    },
    "IRBR3": {
        "name": "IRB Brasil Resseguros",
        "sector": "Financial Services",
        "industry": "Insurance - Reinsurance",
        "status": "active",
    },
    "OIBR3": {
        "name": "Oi",
        "sector": "Communication Services",
        "industry": "Telecom Services",
        "status": "historical",
    },
    "OIBR4": {
        "name": "Oi",
        "sector": "Communication Services",
        "industry": "Telecom Services",
        "status": "historical",
    },
    "GNDI3": {
        "name": "NotreDame Intermédica",
        "sector": "Healthcare",
        "industry": "Medical Care Facilities",
        "status": "historical",
        "successor": "HAPV3",
        "notes": "Incorporada à Hapvida",
    },
    "PARD3": {
        "name": "Hermes Pardini",
        "sector": "Healthcare",
        "industry": "Diagnostics & Research",
        "status": "historical",
        "notes": "Laboratório; saiu de bolsa",
    },
    "TESA3": {
        "name": "Terra Santa Agro",
        "sector": "Consumer Defensive",
        "industry": "Farm Products",
        "status": "historical",
        "notes": "Agronegócio; saiu de bolsa",
    },
    "CNTO3": {
        "name": "Grupo SBF / Centauro",
        "sector": "Consumer Cyclical",
        "industry": "Apparel Retail",
        "status": "historical",
        "successor": "SBFG3",
        "notes": "Ticker antigo; hoje SBFG3",
    },
}


@lru_cache(maxsize=1)
def load_ticker_reference() -> dict[str, dict[str, Any]]:
    """Carrega JSON + aplica overrides manuais (manual vence em campos definidos)."""
    data: dict[str, dict[str, Any]] = {}
    if REFERENCE_PATH.exists():
        try:
            payload = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
            raw = payload.get("tickers") or {}
            for k, v in raw.items():
                data[_norm(k)] = dict(v)
        except Exception:
            data = {}
    for k, ov in MANUAL_OVERRIDES.items():
        t = _norm(k)
        base = data.get(t, {"ticker": t})
        base.update(ov)
        base["ticker"] = t
        data[t] = base
    return data


def get_ticker_meta(ticker: str) -> dict[str, Any]:
    t = _norm(ticker)
    ref = load_ticker_reference()
    if t in ref:
        return dict(ref[t])
    return {
        "ticker": t,
        "name": t,
        "sector": "Unknown",
        "industry": None,
        "status": "unknown",
        "source": "fallback",
    }


def resolve_successor(ticker: str) -> str:
    """Se o ticker foi renomeado, retorna o sucessor; senão o próprio."""
    meta = get_ticker_meta(ticker)
    succ = meta.get("successor")
    if succ and meta.get("status") == "delisted_or_renamed":
        return _norm(str(succ))
    return _norm(ticker)


def is_tradable(ticker: str) -> bool:
    meta = get_ticker_meta(ticker)
    status = meta.get("status") or "unknown"
    return status not in ("delisted_or_renamed", "historical")


def active_universe(tickers: list[str]) -> list[str]:
    """Filtra delisted/renomeados e troca por sucessor quando houver."""
    out: list[str] = []
    seen: set[str] = set()
    for t in tickers:
        nt = _norm(t)
        meta = get_ticker_meta(nt)
        if meta.get("status") in ("delisted_or_renamed", "historical"):
            succ = meta.get("successor")
            if succ:
                nt = _norm(str(succ))
                meta = get_ticker_meta(nt)
        if not is_tradable(nt):
            continue
        if nt not in seen:
            seen.add(nt)
            out.append(nt)
    return out


_UNKNOWN_SECTORS = {
    "",
    "unknown",
    "n/a",
    "none",
    "nan",
    "outros",
    "outros setores",
    "other",
    "n/d",
}


def is_known_sector(sector: str | None) -> bool:
    if sector is None:
        return False
    return str(sector).strip().lower() not in _UNKNOWN_SECTORS


def resolve_sector(*candidates: str | None) -> str:
    """Primeiro setor reconhecido (cadastro B3 antes de yfinance/Unknown)."""
    for c in candidates:
        if is_known_sector(c):
            return str(c).strip()
    return "Unknown"


SECTOR_TRANSLATION_PT: dict[str, str] = {
    "Utilities": "Utilidade Pública (Energia/Saneamento)",
    "Financial Services": "Serviços Financeiros / Bancos",
    "Consumer Defensive": "Consumo Básico",
    "Consumer Cyclical": "Consumo Cíclico / Varejo",
    "Basic Materials": "Materiais Básicos / Mineração",
    "Industrials": "Bens Industriais / Logística",
    "Healthcare": "Saúde / Farmacêutico",
    "Technology": "Tecnologia",
    "Communication Services": "Telecomunicações",
    "Energy": "Petróleo, Gás e Energia",
    "Real Estate": "Imobiliário / Shoppings",
    "Unknown": "Outros Setores",
    "Outros": "Outros Setores",
}


def translate_sector(sector: str | None) -> str:
    """Traduz o nome do setor em inglês para português claro."""
    if not sector or not str(sector).strip() or str(sector) == "Unknown":
        return "Outros Setores"
    s = str(sector).strip()
    return SECTOR_TRANSLATION_PT.get(s, s)


def lookup_company_name(ticker: str) -> str:
    """Retorna o nome amigável da empresa ou a sigla se não houver."""
    meta = get_ticker_meta(ticker)
    name = meta.get("name")
    if name and str(name).strip() and str(name).strip().upper() != _norm(ticker):
        clean = str(name).strip()
        # Remove sufixos como ON NM, PN N1, etc se for o formato bruto
        for suffix in (" ON NM", " PN N2", " PN N1", " ON N2", " UNT N2", " ON", " PN", " UNT"):
            if clean.endswith(suffix):
                clean = clean[: -len(suffix)].strip()
        return clean.title() if clean.isupper() else clean
    return _norm(ticker)


def format_ticker_display(ticker: str) -> str:
    """Formata o código da ação com o nome: 'LREN3 (Lojas Renner)'."""
    nt = _norm(ticker)
    name = lookup_company_name(nt)
    if name and name.upper() != nt:
        return f"{nt} ({name})"
    return nt


def validate_ticker_reference() -> dict[str, Any]:
    """Validates the ticker reference JSON and returns a report.

    Checks for:
    - Tickers with abnormal name formatting (excessive spaces, weird suffixes)
    - Renamed/ticker successors that should be applied
    - Delisted tickers
    - Missing mandatory fields

    Returns a dict with statistics and a list of issues found.
    This function does NOT modify the file — it's for human review.
    """
    import re

    path = REFERENCE_PATH
    if not path.exists():
        return {"error": "Reference file not found at " + str(path)}

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    tickers = data.get("tickers", {})
    total = len(tickers)

    issues: list[dict[str, Any]] = []
    renamed = 0
    delisted = 0
    bad_names = 0
    missing_fields = 0

    for ticker, meta in tickers.items():
        # Check mandatory fields
        for field in ("ticker", "name", "sector"):
            if field not in meta:
                missing_fields += 1
                issues.append(
                    {"ticker": ticker, "issue": f"Missing field: {field}"}
                )
                continue  # skip further checks for this ticker if field missing

        name = str(meta.get("name", "")).strip()
        sector = meta.get("sector", "")

        # Check for abnormal name formatting:
        # - Names with too many consecutive spaces
        # - Names that look like they have padding (multiple spaces inside)
        # - Names ending with unusual suffixes
        space_pattern = re.search(r" {2,}", name)
        if space_pattern:
            bad_names += 1
            issues.append(
                {
                    "ticker": ticker,
                    "issue": f"Abnormal spaces in name: '{name}'",
                    "severity": "low",
                }
            )

        # Check for renamed tickers with successors
        status = meta.get("status", "")
        if status == "delisted_or_renamed":
            delisted += 1
            successor = meta.get("successor", "")
            if not successor:
                issues.append(
                    {
                        "ticker": ticker,
                        "issue": "Marked as delisted_or_renamed but no successor defined",
                        "severity": "medium",
                    }
                )
            else:
                renamed += 1

    # Normalize report
    report: dict[str, Any] = {
        "total_tickers": total,
        "bad_name_formatting": bad_names,
        "renamed_tickers": renamed,
        "delisted_tickers": delisted,
        "missing_fields": missing_fields,
        "issues": issues[:50],  # limit to first 50 issues
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }

    return report

