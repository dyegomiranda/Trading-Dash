"""Download e consolidação de dados abertos da CVM (DFP / ITR / FCA).

Fonte: https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/

O JSON versionado ``data/reference/pit_snapshots.json`` começa como **semente
curada** (para o motor PIT funcionar offline). Este script é o caminho honesto
para substituí-lo por contas oficiais:

    python scripts/download_cvm_data.py --summary
    python scripts/download_cvm_data.py --years 2020-2025 --download
    python scripts/download_cvm_data.py --years 2020-2025 --build

``--download`` busca os ZIP (dezenas de MB por ano) em ``data/cache/cvm/``.
``--build`` parseia o cache e **reescreve** ``pit_snapshots.json``.
Sem ZIPs no cache, ``--build`` **não** apaga a semente.

A CVM não publica preço nem dividend yield. O backtest completa esses campos
com o pregão do dia (TTM de dividendos / fechamento).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.cvm import (  # noqa: E402
    CVM_CACHE,
    build_pit_from_cache,
    download_year,
    parse_years_arg,
)
from src.data.pit_loader import (  # noqa: E402
    PIT_SNAPSHOTS_PATH,
    get_pit_coverage_summary,
    get_pit_origin,
    load_pit_meta,
)


def show_summary() -> None:
    meta = load_pit_meta()
    summary = get_pit_coverage_summary()
    print("\n--- Point-in-time (TradingDash) ---")
    print(f"Arquivo: {PIT_SNAPSHOTS_PATH}")
    print(f"Origem:  {meta.get('origin') or '—'}")
    if meta.get("origin_note"):
        print(f"Nota:    {meta['origin_note']}")
    print(f"Trimestres: {summary['n_quarters']}")
    if summary["n_quarters"] > 0:
        print(f"Período:    {summary['start_date']} → {summary['end_date']}")
        print(f"Tickers:    {summary['tickers_count']}")
        shown = ", ".join(summary["tickers"][:18])
        extra = "…" if summary["tickers_count"] > 18 else ""
        print(f"Empresas:   {shown}{extra}")
    print(f"Cache CVM:  {CVM_CACHE}")
    if CVM_CACHE.exists():
        zips = sorted(p.name for p in CVM_CACHE.glob("*.zip"))
        print(f"ZIPs:       {len(zips)}")
        for name in zips[:12]:
            print(f"  - {name}")
        if len(zips) > 12:
            print(f"  … +{len(zips) - 12}")
    print("-----------------------------------\n")
    if not str(meta.get("origin") or "").startswith("cvm"):
        print(
            "Esta base ainda NÃO é parse da CVM. Para promover:\n"
            "  python scripts/download_cvm_data.py --years 2020-2025 --download\n"
            "  python scripts/download_cvm_data.py --years 2020-2025 --build\n"
        )


def validate_file() -> bool:
    if not PIT_SNAPSHOTS_PATH.exists():
        print(f"ERRO: {PIT_SNAPSHOTS_PATH} não encontrado.")
        return False
    origin = get_pit_origin()
    summary = get_pit_coverage_summary()
    if summary["n_quarters"] <= 0:
        print("ERRO: JSON sem trimestres.")
        return False
    print(f"OK: {summary['n_quarters']} trimestres · origem={origin}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Utilitário de dados abertos CVM (Point-in-Time)."
    )
    parser.add_argument("--summary", action="store_true", help="Resumo da base PIT atual.")
    parser.add_argument("--validate", action="store_true", help="Valida o JSON de snapshots.")
    parser.add_argument(
        "--years",
        default="",
        help="Anos (2020-2025 ou 2022,2023). Padrão: 2020 até o ano corrente.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Baixa ZIPs DFP/ITR/FCA para data/cache/cvm/.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Parseia o cache e reescreve pit_snapshots.json (não baixa).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Com --download, baixa de novo mesmo se o ZIP já existir.",
    )
    args = parser.parse_args()

    if args.summary or (not args.validate and not args.download and not args.build):
        show_summary()
        if not (args.validate or args.download or args.build):
            return 0

    if args.validate:
        if not validate_file():
            return 1

    years = parse_years_arg(args.years)
    if args.download:
        print(f"Baixando CVM anos {years[0]}–{years[-1]}…")
        for year in years:
            try:
                files = download_year(year, force=args.force)
                print(f"  {year}: " + ", ".join(f"{k}={p.name}" for k, p in files.items()))
            except Exception as e:
                print(f"  {year}: FALHA ({e})")
                return 1

    if args.build:
        print(f"Gerando PIT a partir do cache ({years[0]}–{years[-1]})…")
        result = build_pit_from_cache(years)
        if not result.get("ok"):
            print(f"ERRO: {result.get('reason')}")
            print("A semente curada NÃO foi apagada. Rode --download antes.")
            return 1
        print(
            f"OK: {result['n_quarters']} trimestres, {result['n_rows']} linhas, "
            f"{len(result.get('tickers') or [])} tickers → {result['path']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
