"""Download e parse de DFP/ITR da CVM (dados abertos).

O que este módulo **consegue** extrair dos ZIP oficiais:
- ROE (lucro anualizado / patrimônio líquido)
- margem líquida (lucro / receita)
- dívida / patrimônio (empréstimos − caixa) / PL

O que a CVM **não** traz (e o app não inventa):
- preço de mercado, P/L, dividend yield

O motor de simulação completa DY com o TTM dos dividendos históricos
no dia do rebalance e o preço com o fechamento daquele dia.

Fontes:
- https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/
- https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/
- https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FCA/DADOS/
"""

from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.request import Request, urlopen

import pandas as pd

from src.config import DATA_DIR
from src.data.pit_loader import PIT_SNAPSHOTS_PATH
from src.data.universe import normalize_ticker

CVM_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA"
DFP_ZIP = CVM_BASE + "/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"
ITR_ZIP = CVM_BASE + "/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"
FCA_ZIP = CVM_BASE + "/DOC/FCA/DADOS/fca_cia_aberta_{year}.zip"
CAD_CSV = CVM_BASE + "/CAD/DADOS/cad_cia_aberta.csv"

CVM_CACHE = DATA_DIR / "cache" / "cvm"
TICKER_MAP_PATH = DATA_DIR / "reference" / "cvm_ticker_map.json"

_UA = {
    "User-Agent": (
        "TradingDash/1.4 (educational paper-trading; "
        "+https://github.com/dyegomiranda/Trading-Dash)"
    )
}

# Contas CVM usadas (código hierárquico). Preferimos consolidado.
_DRE_REVENUE = ("3.01",)
_DRE_EBIT = ("3.05",)
_DRE_NET_INCOME = ("3.11", "3.09", "3.11.01")
_BPP_EQUITY = ("2.03",)
_BPP_DEBT_ST = ("2.01.04",)
_BPP_DEBT_LT = ("2.02.01",)
_BPA_CASH = ("1.01.01",)

def digits_cnpj(value: Any) -> str:
    raw = re.sub(r"\D", "", str(value or ""))
    return raw.zfill(14) if raw else ""


def load_static_ticker_map() -> dict[str, str]:
    if not TICKER_MAP_PATH.exists():
        return {}
    try:
        data = json.loads(TICKER_MAP_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw = data.get("map") or {}
    out: dict[str, str] = {}
    for cnpj, ticker in raw.items():
        key = digits_cnpj(cnpj)
        t = normalize_ticker(str(ticker))
        if key and t:
            out[key] = t
    return out


def cvm_cache_dir() -> Path:
    CVM_CACHE.mkdir(parents=True, exist_ok=True)
    return CVM_CACHE


def download_url(url: str, dest: Path, *, timeout: int = 180) -> Path:
    """Baixa ``url`` para ``dest`` (cria pastas). Não inventa conteúdo."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers=_UA)
    with urlopen(req, timeout=timeout) as resp, dest.open("wb") as fh:
        shutil.copyfileobj(resp, fh)
    return dest


def dfp_url(year: int) -> str:
    return DFP_ZIP.format(year=int(year))


def itr_url(year: int) -> str:
    return ITR_ZIP.format(year=int(year))


def fca_url(year: int) -> str:
    return FCA_ZIP.format(year=int(year))


def zip_name(kind: str, year: int) -> str:
    return f"{kind}_cia_aberta_{int(year)}.zip"


def annualize_factor(dt_ini: pd.Timestamp | None, dt_fim: pd.Timestamp | None) -> float:
    """ITR é acumulado no exercício; anualiza pelo número de meses."""
    if dt_ini is None or dt_fim is None or pd.isna(dt_ini) or pd.isna(dt_fim):
        return 1.0
    days = max(1, int((pd.Timestamp(dt_fim) - pd.Timestamp(dt_ini)).days) + 1)
    months = max(1.0, min(12.0, days / 30.437))
    return 12.0 / months


def _read_cvm_csv(raw: bytes) -> pd.DataFrame:
    for enc in ("latin-1", "utf-8", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            text = None
    else:
        text = raw.decode("latin-1", errors="replace")
    buf = io.StringIO(text)
    df = pd.read_csv(buf, sep=";", dtype=str, low_memory=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _pick_col(df: pd.DataFrame, *candidates: str) -> str | None:
    cols = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in cols:
            return cols[name.lower()]
    for key, orig in cols.items():
        for name in candidates:
            if name.lower() in key:
                return orig
    return None


def _to_float_series(s: pd.Series) -> pd.Series:
    cleaned = (
        s.astype(str)
        .str.strip()
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    # Se não havia milhar (só um ponto decimal original), a troca acima quebra.
    # Detecta: original com um único ponto e sem vírgula → usa o original.
    raw = s.astype(str).str.strip()
    simple = raw.str.match(r"^-?\d+(\.\d+)?$")
    out = pd.to_numeric(cleaned, errors="coerce")
    simple_vals = pd.to_numeric(raw.where(simple), errors="coerce")
    return simple_vals.fillna(out)


def _filter_ultimo(df: pd.DataFrame) -> pd.DataFrame:
    col = _pick_col(df, "ORDEM_EXERC")
    if not col:
        return df
    mask = df[col].astype(str).str.upper().str.contains("LTIMO", na=False)
    if mask.any():
        return df.loc[mask].copy()
    return df


def _prefer_consolidado(df: pd.DataFrame) -> pd.DataFrame:
    col = _pick_col(df, "GRUPO_DF")
    if not col:
        return df
    cons = df[col].astype(str).str.contains("Consolidado", case=False, na=False)
    if cons.any():
        return df.loc[cons].copy()
    return df


def _conta_matches(code: str, prefixes: tuple[str, ...]) -> bool:
    c = str(code or "").strip()
    for p in prefixes:
        if c == p or c.startswith(p + "."):
            # Evita 3.01.01 quando pedimos exatamente o agregado 3.01
            if c == p:
                return True
            # Para 3.11.01 (lucro dos controladores) aceitamos o prefixo listado.
            if p in ("3.11", "3.09") and c.startswith(p):
                return True
    return False


def extract_accounts(df: pd.DataFrame, roles: dict[str, tuple[str, ...]]) -> pd.DataFrame:
    """Reduz um CSV CVM (DRE/BPA/BPP) a uma linha por CNPJ+data com contas nomeadas."""
    if df is None or df.empty:
        return pd.DataFrame()
    df = _filter_ultimo(df)
    df = _prefer_consolidado(df)
    cnpj_c = _pick_col(df, "CNPJ_CIA")
    date_c = _pick_col(df, "DT_REFER")
    conta_c = _pick_col(df, "CD_CONTA")
    valor_c = _pick_col(df, "VL_CONTA")
    name_c = _pick_col(df, "DENOM_CIA", "Nome_Empresarial")
    ini_c = _pick_col(df, "DT_INI_EXERC")
    fim_c = _pick_col(df, "DT_FIM_EXERC")
    if not (cnpj_c and date_c and conta_c and valor_c):
        return pd.DataFrame()

    work = df[[cnpj_c, date_c, conta_c, valor_c]].copy()
    work.columns = ["cnpj_raw", "dt_refer", "cd_conta", "vl_conta"]
    if name_c:
        work["name"] = df[name_c].astype(str)
    if ini_c:
        work["dt_ini"] = pd.to_datetime(df[ini_c], errors="coerce")
    if fim_c:
        work["dt_fim"] = pd.to_datetime(df[fim_c], errors="coerce")
    work["cnpj"] = work["cnpj_raw"].map(digits_cnpj)
    work["dt_refer"] = pd.to_datetime(work["dt_refer"], errors="coerce").dt.strftime("%Y-%m-%d")
    work["valor"] = _to_float_series(work["vl_conta"])
    work = work[work["cnpj"] != ""]
    work = work[work["dt_refer"] != "NaT"]

    rows: list[dict[str, Any]] = []
    grouped = work.groupby(["cnpj", "dt_refer"], sort=False)
    for (cnpj, dt_refer), g in grouped:
        rec: dict[str, Any] = {
            "cnpj": cnpj,
            "as_of": dt_refer,
            "name": str(g["name"].dropna().iloc[0]) if "name" in g.columns and g["name"].notna().any() else "",
        }
        if "dt_ini" in g.columns:
            rec["dt_ini"] = g["dt_ini"].dropna().iloc[0] if g["dt_ini"].notna().any() else None
        if "dt_fim" in g.columns:
            rec["dt_fim"] = g["dt_fim"].dropna().iloc[0] if g["dt_fim"].notna().any() else None
        for role, prefixes in roles.items():
            exact = g[g["cd_conta"].astype(str).str.strip().isin(prefixes)]
            if exact.empty:
                # fallback: primeiro código que casa o prefixo listado
                mask = g["cd_conta"].map(lambda c: _conta_matches(str(c), prefixes))
                exact = g[mask]
            if exact.empty:
                rec[role] = None
                continue
            rec[role] = float(exact["valor"].iloc[0])
        rows.append(rec)
    return pd.DataFrame(rows)


def parse_statement_csv(raw: bytes, kind: str) -> pd.DataFrame:
    df = _read_cvm_csv(raw)
    if kind == "dre":
        roles = {"receita": _DRE_REVENUE, "ebit": _DRE_EBIT, "lucro": _DRE_NET_INCOME}
    elif kind == "bpp":
        roles = {
            "pl": _BPP_EQUITY,
            "divida_cp": _BPP_DEBT_ST,
            "divida_lp": _BPP_DEBT_LT,
        }
    elif kind == "bpa":
        roles = {"caixa": _BPA_CASH}
    else:
        raise ValueError(f"kind desconhecido: {kind}")
    return extract_accounts(df, roles)


def _zip_member_kind(name: str) -> str | None:
    n = name.lower()
    if "dre" in n and "con" in n:
        return "dre"
    if "bpp" in n and "con" in n:
        return "bpp"
    if "bpa" in n and "con" in n:
        return "bpa"
    return None


def parse_cvm_zip(zip_path: Path | bytes, *, source: str) -> pd.DataFrame:
    """Lê um ZIP DFP/ITR e devolve uma linha por CNPJ+data com contas mescladas."""
    if isinstance(zip_path, (bytes, bytearray)):
        zf = zipfile.ZipFile(io.BytesIO(zip_path))
    else:
        zf = zipfile.ZipFile(zip_path)
    pieces: dict[str, list[pd.DataFrame]] = {"dre": [], "bpp": [], "bpa": []}
    with zf:
        for info in zf.infolist():
            kind = _zip_member_kind(info.filename)
            if not kind:
                continue
            raw = zf.read(info.filename)
            part = parse_statement_csv(raw, kind)
            if not part.empty:
                pieces[kind].append(part)
    frames = {k: pd.concat(v, ignore_index=True) if v else pd.DataFrame() for k, v in pieces.items()}
    base = frames["dre"]
    if base.empty:
        return pd.DataFrame()
    out = base
    for other in ("bpp", "bpa"):
        extra = frames[other]
        if extra.empty:
            continue
        cols = [c for c in extra.columns if c not in ("name", "dt_ini", "dt_fim")]
        extra = extra[cols]
        out = out.merge(extra, on=["cnpj", "as_of"], how="left")
    out["source"] = source
    return out


def parse_fca_tickers(zip_path: Path | bytes) -> dict[str, str]:
    """CNPJ → ticker a partir do FCA (valor mobiliário)."""
    if isinstance(zip_path, (bytes, bytearray)):
        zf = zipfile.ZipFile(io.BytesIO(zip_path))
    else:
        zf = zipfile.ZipFile(zip_path)
    mapping: dict[str, list[str]] = {}
    with zf:
        members = [i for i in zf.infolist() if "valor_mobiliario" in i.filename.lower()]
        if not members:
            members = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
        for info in members:
            raw = zf.read(info.filename)
            try:
                df = _read_cvm_csv(raw)
            except Exception:
                continue
            cnpj_c = _pick_col(df, "CNPJ_CIA")
            tick_c = _pick_col(df, "Codigo_Negociacao", "CD_NEGOCIACAO", "Ticker")
            if not (cnpj_c and tick_c):
                continue
            for _, row in df[[cnpj_c, tick_c]].iterrows():
                cnpj = digits_cnpj(row[cnpj_c])
                ticker = normalize_ticker(str(row[tick_c] or ""))
                if not cnpj or not ticker or not re.match(r"^[A-Z]{4}\d{1,2}$", ticker):
                    continue
                mapping.setdefault(cnpj, [])
                if ticker not in mapping[cnpj]:
                    mapping[cnpj].append(ticker)
    static = load_static_ticker_map()
    out: dict[str, str] = dict(static)
    for cnpj, tickers in mapping.items():
        if cnpj in static:
            continue
        preferred = [t for t in tickers if t.endswith(("4", "3", "11", "6", "5"))]
        out[cnpj] = preferred[0] if preferred else tickers[0]
    return out


def statements_to_fundamentals(
    statements: pd.DataFrame,
    ticker_map: dict[str, str],
    *,
    names_by_ticker: dict[str, dict[str, str]] | None = None,
) -> pd.DataFrame:
    """Converte contas CVM em linhas no contrato FUNDAMENTALS (sem preço/DY)."""
    if statements is None or statements.empty:
        return pd.DataFrame()
    names_by_ticker = names_by_ticker or {}
    rows: list[dict[str, Any]] = []
    for rec in statements.to_dict(orient="records"):
        cnpj = digits_cnpj(rec.get("cnpj"))
        ticker = ticker_map.get(cnpj)
        if not ticker:
            continue
        pl = rec.get("pl")
        lucro = rec.get("lucro")
        receita = rec.get("receita")
        factor = annualize_factor(rec.get("dt_ini"), rec.get("dt_fim"))
        roe = None
        net_margin = None
        try:
            pl_f = float(pl) if pl is not None and not pd.isna(pl) else None
        except (TypeError, ValueError):
            pl_f = None
        try:
            lucro_f = float(lucro) if lucro is not None and not pd.isna(lucro) else None
        except (TypeError, ValueError):
            lucro_f = None
        try:
            rec_f = float(receita) if receita is not None and not pd.isna(receita) else None
        except (TypeError, ValueError):
            rec_f = None
        if pl_f and pl_f != 0 and lucro_f is not None:
            roe = (lucro_f * factor) / pl_f
        if rec_f and rec_f != 0 and lucro_f is not None:
            net_margin = lucro_f / rec_f
        debt = 0.0
        for k in ("divida_cp", "divida_lp"):
            v = rec.get(k)
            try:
                if v is not None and not pd.isna(v):
                    debt += float(v)
            except (TypeError, ValueError):
                pass
        caixa = 0.0
        try:
            if rec.get("caixa") is not None and not pd.isna(rec.get("caixa")):
                caixa = float(rec["caixa"])
        except (TypeError, ValueError):
            caixa = 0.0
        net_debt = debt - caixa
        debt_equity = (net_debt / pl_f) if pl_f and pl_f != 0 else None
        meta = names_by_ticker.get(ticker, {})
        rows.append(
            {
                "ticker": ticker,
                "name": meta.get("name") or rec.get("name") or ticker,
                "sector": meta.get("sector") or "",
                "roe": roe,
                "net_margin": net_margin,
                "debt_equity": debt_equity,
                "fcf_positive": None,
                "source": rec.get("source") or "cvm",
                "data_quality": "cvm_pit",
                "as_of": rec.get("as_of"),
            }
        )
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    # Um ticker pode aparecer mais de uma vez (ON/PN map, DFP+ITR). Fica a última.
    out = out.sort_values(["as_of", "ticker"]).drop_duplicates(
        subset=["as_of", "ticker"], keep="last"
    )
    return out


def fundamentals_to_quarters(df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if df is None or df.empty:
        return {}
    quarters: dict[str, list[dict[str, Any]]] = {}
    for as_of, g in df.groupby("as_of"):
        key = str(as_of)
        records = []
        for rec in g.to_dict(orient="records"):
            clean = {k: v for k, v in rec.items() if v is not None and not (isinstance(v, float) and pd.isna(v))}
            records.append(clean)
        if records:
            quarters[key] = records
    return dict(sorted(quarters.items()))


def write_pit_snapshots(
    quarters: dict[str, list[dict[str, Any]]],
    *,
    dest: Path | None = None,
    origin: str = "cvm_dfp_itr",
    extra_meta: dict[str, Any] | None = None,
) -> Path:
    dest = dest or PIT_SNAPSHOTS_PATH
    payload: dict[str, Any] = {
        "description": (
            "Snapshots point-in-time gerados a partir de DFP/ITR da CVM. "
            "Só contas (ROE/margem/alavancagem). Preço e dividend yield NÃO vêm da CVM."
        ),
        "version": "2.0.0",
        "updated_at": date.today().isoformat(),
        "origin": origin,
        "origin_note": (
            "Parser CVM (dados.cvm.gov.br). DY e preço no backtest usam o pregão "
            "do dia (TTM de dividendos / fechamento), sem look-ahead de mercado."
        ),
        "quarters": quarters,
    }
    if extra_meta:
        payload.update(extra_meta)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def download_year(year: int, *, kinds: Iterable[str] = ("dfp", "itr", "fca"), force: bool = False) -> dict[str, Path]:
    cache = cvm_cache_dir()
    urls = {"dfp": dfp_url, "itr": itr_url, "fca": fca_url}
    out: dict[str, Path] = {}
    for kind in kinds:
        dest = cache / zip_name(kind, year)
        if dest.exists() and dest.stat().st_size > 0 and not force:
            out[kind] = dest
            continue
        url = urls[kind](year)
        download_url(url, dest)
        out[kind] = dest
    return out


def build_pit_from_cache(
    years: Iterable[int],
    *,
    dest: Path | None = None,
) -> dict[str, Any]:
    """Parseia ZIPs em cache e grava ``pit_snapshots.json``. Não baixa nada."""
    from src.data.reference import get_ticker_meta

    ticker_map = load_static_ticker_map()
    frames: list[pd.DataFrame] = []
    used: list[str] = []
    cache = cvm_cache_dir()
    for year in years:
        fca = cache / zip_name("fca", year)
        if fca.exists():
            try:
                ticker_map.update(parse_fca_tickers(fca))
            except Exception:
                pass
        for kind, source in (("dfp", "cvm_dfp"), ("itr", "cvm_itr")):
            path = cache / zip_name(kind, year)
            if not path.exists():
                continue
            try:
                part = parse_cvm_zip(path, source=source)
            except Exception:
                continue
            if part.empty:
                continue
            frames.append(part)
            used.append(path.name)

    if not frames:
        return {"ok": False, "reason": "nenhum ZIP DFP/ITR parseável no cache", "files": []}

    statements = pd.concat(frames, ignore_index=True)
    names: dict[str, dict[str, str]] = {}
    for t in set(ticker_map.values()):
        meta = get_ticker_meta(t)
        names[t] = {"name": str(meta.get("name") or t), "sector": str(meta.get("sector") or "")}
    fund = statements_to_fundamentals(statements, ticker_map, names_by_ticker=names)
    quarters = fundamentals_to_quarters(fund)
    path = write_pit_snapshots(
        quarters,
        dest=dest,
        extra_meta={"cvm_files": used, "n_tickers_mapped": len(ticker_map)},
    )
    from src.data.pit_loader import load_pit_fundamentals

    load_pit_fundamentals.cache_clear()
    n_rows = int(sum(len(v) for v in quarters.values()))
    return {
        "ok": True,
        "path": str(path),
        "n_quarters": len(quarters),
        "n_rows": n_rows,
        "files": used,
        "tickers": sorted({r["ticker"] for rows in quarters.values() for r in rows if "ticker" in r}),
    }


def parse_years_arg(raw: str, *, default_start: int = 2020) -> list[int]:
    raw = (raw or "").strip()
    if not raw:
        return list(range(default_start, date.today().year + 1))
    if "-" in raw and "," not in raw:
        a, b = raw.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x.strip()) for x in raw.split(",") if x.strip()]
