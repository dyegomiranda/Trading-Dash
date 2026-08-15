"""Configurações globais da tese Quality Dividend e do paper trading."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
PORTFOLIO_DIR = DATA_DIR / "portfolio"
SCORE_HISTORY_DIR = DATA_DIR / "scores"


# Versão da tese — grava em carteiras/projeções para reprodutibilidade
THESIS_ID = "quality_dividend"
THESIS_VERSION = "1.4.0"
THESIS_LABEL = "Quality Dividend (renda com qualidade)"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    brapi_token: str | None = Field(default=None, alias="BRAPI_TOKEN")
    # Default mais realista para iniciante (pode mudar no app)
    paper_initial_cash: float = Field(default=10_000.0, alias="PAPER_INITIAL_CASH")
    # Internacionalização leve: "pt_BR" (padrão) ou "en_US". Controla o hook de
    # formatação (separadores de milhar/decimal e símbolo de moeda).
    locale: str = Field(default="pt_BR", alias="LOCALE")
    cache_ttl_hours: int = 12
    # TTL por tipo de dado (horas). Sobrescreve cache_ttl_hours quando o kind
    # existe. Tipos: "benchmark", "fundamentals", "prices", "dividends",
    # "macro", "brapi_quote". Dados "vivos" (preços) vencem antes; referências
    # (benchmark/macro) ficam mais tempo.
    cache_ttl_kind_hours: dict[str, int] = Field(
        default_factory=lambda: {
            "benchmark": 24,
            "macro": 6,
            "fundamentals": 12,
            "prices": 6,
            "dividends": 24,
            "brapi_quote": 6,
        },
        alias="CACHE_TTL_KIND_HOURS",
    )
    default_top_n: int = 15
    core_weight: float = 0.70
    satellite_weight: float = 0.30
    max_position_pct: float = 0.10
    max_sector_pct: float = 0.30  # diversificação: teto por setor na carteira modelo
    rebalance_min_score: float = 55.0
    preferred_dy_min: float = 0.04
    preferred_dy_max: float = 0.12
    # DY acima disso com sinais fracos = armadilha de yield (penaliza score)
    high_yield_trap: float = 0.14
    min_roe: float = 0.12
    max_net_debt_ebitda: float = 3.0
    min_payout: float = 0.20
    max_payout: float = 0.85
    # Projeção de renda: teto de taxa de dividendo no longo prazo
    projection_max_yield: float = 0.10
    yfinance_timeout: int = 20
    # Limite de tickers por fetch Yahoo (evita travar a UI)
    yfinance_max_tickers: int = Field(default=40, alias="YFINANCE_MAX_TICKERS")
    yfinance_workers: int = Field(default=8, alias="YFINANCE_WORKERS")
    yfinance_ticker_timeout: float = Field(default=4.0, alias="YFINANCE_TICKER_TIMEOUT")
    news_timeout_sec: float = Field(default=8.0, alias="NEWS_TIMEOUT_SEC")
    # Regime macro: "auto" (busca Selic/IPCA no Banco Central) | "expansionary" |
    # "cautious" | "restrictive" (manual) | "off" (desliga inclinação setorial).
    macro_override: str = Field(default="off", alias="MACRO_OVERRIDE")


# Universo líquido prioritário (scan rápido na Bolsa real)
B3_CORE_SCAN: list[str] = [
    "ITUB4",
    "BBDC4",
    "BBAS3",
    "SANB11",
    "BPAC11",
    "B3SA3",
    "BBSE3",
    "CXSE3",
    "PSSA3",
    "AXIA3",
    "CMIG4",
    "CPLE3",
    "CPFE3",
    "ENGI11",
    "EGIE3",
    "TAEE11",
    "EQTL3",
    "SBSP3",
    "SAPR11",
    "CSMG3",
    "VIVT3",
    "TIMS3",
    "ABEV3",
    "LREN3",
    "HYPE3",
    "RADL3",
    "WEGE3",
    "RAIL3",
    "CCRO3",
    "VALE3",
    "GGBR4",
    "CSNA3",
    "SUZB3",
    "KLBN11",
    "PETR4",
    "PRIO3",
    "UGPA3",
    "VBBR3",
    "RENT3",
    "TOTS3",
    "MULT3",
    "IGTI11",
]


# Pesos do score composto (0–100). Soma = 1.0
SCORE_WEIGHTS: dict[str, float] = {
    "quality": 0.35,
    "dividends": 0.30,
    "financial_health": 0.20,
    "valuation": 0.15,
}

# Setores preferenciais (core) vs satélite no Brasil
CORE_SECTORS = {
    "Utilities",
    "Financial Services",
    "Financials",
    "Banks",
    "Insurance",
    "Communication Services",
    "Telecom",
    "Electric Utilities",
    "Regulated Electric",
    "Water Utilities",
    "Consumer Defensive",
    "Consumer Staples",
}

SATELLITE_SECTORS = {
    "Industrials",
    "Basic Materials",
    "Energy",
    "Healthcare",
    "Real Estate",
    "Consumer Cyclical",
    "Technology",
}

# Universo amplo B3 (tickers sem .SA). Filtros da tese reduzem depois.
B3_UNIVERSE: list[str] = [
    # Bancos / Financeiro
    "ITUB4",
    "ITUB3",
    "BBDC4",
    "BBDC3",
    "BBAS3",
    "SANB11",
    "BPAC11",
    "BPAN4",
    "BRSR6",
    "ABCB4",
    "PINE4",
    "B3SA3",
    "BBSE3",
    "CXSE3",
    "PSSA3",
    "WIZC3",
    "IRBR3",
    # Energia / Utilities (ELET3/ELET6 migraram para AXIA)
    "AXIA3",
    "CMIG4",
    "CMIG3",
    "CPLE6",
    "CPLE3",
    "CPFE3",
    "ENGI11",
    "EGIE3",
    "TAEE11",
    "TAEE4",
    "TRPL4",
    "NEOE3",
    "EQTL3",
    "AURE3",
    "AESB3",
    "ALUP11",
    "SBSP3",
    "SAPR11",
    "SAPR4",
    "CSMG3",
    "CASN3",
    "SMTO3",
    # Telecom
    "VIVT3",
    "TIMS3",
    "OIBR3",
    # Consumo / varejo / defensivos
    "ABEV3",
    "AMER3",
    "MGLU3",
    "LREN3",
    "REDE3",
    "PCAR3",
    "ASAI3",
    "CRFB3",
    "GMAT3",
    "NTCO3",
    "HYPE3",
    "RADL3",
    "FLRY3",
    "HAPV3",
    "QUAL3",
    "MDIA3",
    "SMFT3",
    "VIVA3",
    "SOMA3",
    "ARZZ3",
    "ALPA4",
    "GRND3",
    "VULC3",
    "CAML3",
    "BRFS3",
    "JBSS3",
    "MRFG3",
    "BEEF3",
    "SMTO3",
    # Industrial / logística
    "WEGE3",
    "RAIL3",
    "CCRO3",
    "ECOR3",
    "EMBR3",
    "TUPY3",
    "POMO4",
    "RAPT4",
    "MYPK3",
    "KEPL3",
    "SHUL4",
    "FRAS3",
    "LEVE3",
    "ROMI3",
    "TGMA3",
    "JSLG3",
    "LOGN3",
    "STBP3",
    # Materiais / commodities
    "VALE3",
    "CSNA3",
    "GGBR4",
    "GOAU4",
    "USIM5",
    "CMIN3",
    "SUZB3",
    "KLBN11",
    "KLBN4",
    "RANI3",
    "DXCO3",
    "FESA4",
    "UNIP6",
    "BRAP4",
    # Energia / óleo & gás
    "PETR4",
    "PETR3",
    "PRIO3",
    "RECV3",
    "RRRP3",
    "CSAN3",
    "UGPA3",
    "VBBR3",
    "ENAT3",
    # Construção / real estate
    "CYRE3",
    "MRVE3",
    "EZTC3",
    "TEND3",
    "DIRR3",
    "EVEN3",
    "JHSF3",
    "MULT3",
    "IGTI11",
    "ALSO3",
    "BRML3",
    "LOGG3",
    "HBSA3",
    # Tecnologia / outros
    "TOTS3",
    "LWSA3",
    "CASH3",
    "MELI34",
    "POSI3",
    "INTB3",
    "BMOB3",
    "AERI3",
    # Diversos líquidos
    "RENT3",
    "MOVI3",
    "LCAM3",
    "VAMO3",
    "AZUL4",
    "GOLL4",
    "CVCB3",
    "YDUQ3",
    "COGN3",
    "SEER3",
    "ANIM3",
    "CSED3",
    "SLCE3",
    "AGRO3",
    "TTEN3",
    "SOJA3",
    "JALL3",
    "RAIZ4",
    "BRKM5",
    "DEXP3",
    "ODPV3",
    "ONCO3",
    "AALR3",
    "PARD3",
    "DASA3",
    "RDOR3",
    "MATD3",
    "PNVL3",
    "BLAU3",
    "VITT3",
    "ESPA3",
    "MEAL3",
    "ZAMP3",
    "BKBR3",
    "PETZ3",
    "AMAR3",
    "GUAR3",
    "CEAB3",
    "SBFG3",
    "TFCO4",
    "CBAV3",
    "MLAS3",
    "ORVR3",
    "OPCT3",
    "GGPS3",
    "CLSA3",
    "IFCM3",
    "TRAD3",
    "NGRD3",
    "MODL11",
    "BMGB4",
    "BMGB11",
    "PRNR3",
    "SEQL3",
    "SIMH3",
    "TCSA3",
    "TRIS3",
    "CURY3",
    "PLPL3",
    "MTRE3",
    "HBOR3",
    "GFSA3",
    "RSID3",
    "PDTC3",
    "PTBL3",
    "SHOW3",
    "AMBP3",
    "ORPD3",
]


# Nomes que saíram ou mudaram de ticker — entram no ensaio histórico
# para não fingir que só existiu quem está listado hoje.
B3_HISTORICAL_EXTRA: list[str] = [
    "ELET3",
    "ELET6",
    "LAME3",
    "LAME4",
    "BTOW3",
    "VVAR3",
    "HGTX3",
    "SMLS3",
    "LINX3",
    "BIDI11",
    "BIDI4",
    "IRBR3",
    "OIBR3",
    "OIBR4",
    "GNDI3",
    "PARD3",
    "TESA3",
    "CNTO3",
]


def get_settings() -> Settings:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    SCORE_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
