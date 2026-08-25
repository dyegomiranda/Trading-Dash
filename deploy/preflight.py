"""Pre-flight de deploy — valida que o app sobe em um ambiente limpo (sem rede).

Uso (da raiz do repo, igual ao CI/Cloud):
    python deploy/preflight.py

O que checa:
  1. Dependências instaladas (requirements.txt resolvem).
  2. Referência B3 (data/reference/b3_tickers.json) está versionada no git
     — sem isso, nomes e setores quebram no servidor.
  3. Todos os módulos de src/ importáveis (py_compile de rede-pronto).
  4. Cada página em app_pages/ importa (syntaticamente) sem rede.
  5. O entrypoint app.py SOBE pelo harness AppTest do Streamlit com a fonte
     forçada para "demo" (offline); a página padrão renderiza sem exceção.

Não precisa de conta. Corre em segundos. É o mesmo "contrato" que o
Streamlit Community Cloud executa ao fazer deploy (pip install + streamlit run).
"""

from __future__ import annotations

import contextlib
import importlib
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, ok: bool, why: str = "") -> None:
    mark = "ok " if ok else "FALHA"
    print(f"  [{mark}] {name}" + (f" — {why}" if why and not ok else ""))
    if not ok:
        FAILS.append(f"{name}: {why}")


def main() -> int:
    print("Pre-flight de deploy · TradingDash\n")

    # 1) Dependências essenciais
    print("1) Dependências")
    deps = ["streamlit", "pandas", "numpy", "plotly", "yfinance", "requests", "pydantic", "pydantic_settings"]
    for dep in deps:
        try:
            importlib.import_module(dep)
            check(f"import {dep}", True)
        except Exception as e:  # noqa: BLE001
            check(f"import {dep}", False, str(e))

    # 2) Referência versionada
    print("\n2) Referência B3 e Point-in-Time (deve estar no git)")
    ref = ROOT / "data" / "reference" / "b3_tickers.json"
    if not ref.exists():
        check("data/reference/b3_tickers.json existe", False, "arquivo ausente")
    else:
        try:
            data = json.loads(ref.read_text(encoding="utf-8"))
            check("b3_tickers.json válido (JSON)", isinstance(data, (dict, list)))
            if isinstance(data, dict):
                entries = sum(len(v) if isinstance(v, list) else 1 for v in data.values())
                check("b3_tickers.json contém cadastro", entries > 0, f"{entries} entradas")
        except (json.JSONDecodeError, OSError) as e:
            check("b3_tickers.json válido (JSON)", False, str(e))

    pit_ref = ROOT / "data" / "reference" / "pit_snapshots.json"
    if not pit_ref.exists():
        check("data/reference/pit_snapshots.json existe", False, "arquivo ausente")
    else:
        try:
            pdata = json.loads(pit_ref.read_text(encoding="utf-8"))
            check("pit_snapshots.json válido (JSON)", isinstance(pdata, dict) and "quarters" in pdata)
        except Exception as e:
            check("pit_snapshots.json válido (JSON)", False, str(e))

    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "data/reference/b3_tickers.json"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    ).stdout.strip()
    check("b3_tickers.json versionado no git", bool(tracked))

    # 3) Módulos src/ importáveis
    print("\n3) Importabilidade dos módulos (src/)")
    src_pkg = ROOT / "src"
    mods = sorted(p.relative_to(ROOT).with_suffix("").as_posix().replace("/", ".")
                  for p in src_pkg.rglob("*.py") if "__pycache__" not in p.parts)
    for mod in mods:
        try:
            importlib.import_module(mod)
            check(f"import {mod}", True)
        except Exception as e:  # noqa: BLE001
            check(f"import {mod}", False, str(e)[:160])

    # 4) Páginas compilam
    print("\n4) Páginas (app_pages/)")
    for page in sorted((ROOT / "app_pages").glob("*.py")):
        try:
            py_compile.compile(str(page), doraise=True)
            check(f"py_compile {page.name}", True)
        except Exception as e:  # noqa: BLE001
            check(f"py_compile {page.name}", False, str(e)[:160])

    # 5) App sobe offline com fonte demo (só o harness; a UI não oferece esse modo)
    print("\n5) Boot do app (AppTest, fonte=demo, offline)")
    try:
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
        with contextlib.suppress(Exception):
            at.session_state["allow_demo_provider"] = True
            at.session_state["app_provider"] = "demo"
            at.session_state["onboarding_done"] = True
        at.run()
        if at.exception:
            errs = [str(e.value) for e in at.exception]
            check("app.py sobe sem exceção", False, "; ".join(errs)[:300])
        else:
            check("app.py sobe sem exceção", True)
            n_errors = len([el for el in at.error])
            check("sem bloco st.error", n_errors == 0, f"{n_errors} erros renderizados")
            print(f"    widgets: {len(at.get('selectbox'))} selectbox, "
                  f"{len(at.get('button'))} botões, {len(at.get('dataframe'))} dataframes")
    except Exception as e:  # noqa: BLE001
        check("app.py sobe sem exceção", False, str(e)[:300])

    print("\n" + ("TUDO OK — pronto para deploy." if not FAILS else f"{len(FAILS)} falha(s):"))
    for f in FAILS:
        print(f"  - {f}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    raise SystemExit(main())