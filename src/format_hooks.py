"""Internacionalização leve: hook central de formatação de números e moeda.

A UI é em português (Brasil) — números com vírgula decimal e R$. Para futura
internacionalização, todo número exibido deve passar por **um único lugar**:
este módulo. Trocar ``LOCALE`` de ``"pt_BR"`` para ``"en_US"`` muda o app
inteiro, sem caçar ``f"{x:.2f}"`` espalhado.

Hook (função "de formato") segue o padrão de um formatter simples:
``format_num(value, decimals) -> str`` aplica separador de milhar/decimal pelo
locale. Nada de ``locale.setlocale`` global (frágil em threads); é um
formatador determinístico.

Note: o narrador de tese (`src/thesis/narrative.py`) e serviços ainda usam
f-strings com decimal fixo em alguns trechos — a migração completa é incremental.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

LocaleName = Literal["pt_BR", "en_US"]

# Separadores por locale (milhar, decimal).
_LOCALE_SEP: dict[LocaleName, tuple[str, str]] = {
    "pt_BR": (".", ","),
    "en_US": (",", "."),
}

# Ativo global — ajuste via config/UI, não via import-churn.
ACTIVE_LOCALE: LocaleName = "pt_BR"


def set_active_locale(locale: LocaleName) -> None:
    """Define o locale usado pelo hook de formatação (global)."""
    global ACTIVE_LOCALE
    ACTIVE_LOCALE = locale


def get_active_locale() -> LocaleName:
    return ACTIVE_LOCALE


def _apply_separators(s: str, thousands: str, decimal: str) -> str:
    """Aplica separadores a um número já formatado com ponto decimal."""
    sign = ""
    if s.startswith("-"):
        sign, s = "-", s[1:]
    elif s.startswith("+"):
        s = s[1:]
    int_part, _, dec_part = s.partition(".")
    # agrupa a parte inteira em grupos de 3 da direita
    if int_part:
        grouped: list[str] = []
        while len(int_part) > 3:
            grouped.insert(0, int_part[-3:])
            int_part = int_part[:-3]
        grouped.insert(0, int_part)
        out = thousands.join(grouped)
    else:
        out = "0"
    if dec_part:
        out = f"{out}{decimal}{dec_part}"
    return f"{sign}{out}"


def format_num(value: float | int | None, decimals: int = 2) -> str:
    """Formata um número com separadores do locale ativo."""
    if value is None:
        return "—"
    try:
        text = f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"
    th, dec = _LOCALE_SEP.get(ACTIVE_LOCALE, (",", "."))
    return _apply_separators(text, th, dec)


def format_brl_hook(value: float | None) -> str:
    """Móeda no locale ativo (R$ para pt_BR, $ para en_US)."""
    if value is None:
        return "—"
    rendered = format_num(value, 2)
    if ACTIVE_LOCALE == "en_US":
        return f"$ {rendered}" if rendered != "—" else "—"
    return f"R$ {rendered}"


def format_pct_hook(value: float | None, decimals: int = 1) -> str:
    """Percentual no locale ativo (ex.: ``3,4%`` em pt_BR, ``3.4%`` em en_US)."""
    if value is None:
        return "—"
    return f"{format_num(value * 100.0, decimals)}%"


# Pequena "vtable" para quem prefere injetar um callable (test-friendly).
Formatter = Callable[[float | None], str]