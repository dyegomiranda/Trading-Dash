"""Visual system — dark fintech (Exodus / modern trading dashboard)."""

from __future__ import annotations


import streamlit as st

# Paleta usada em charts e HTML
COLORS = {
    "bg": "#070B14",
    "bg_elevated": "#0F172A",
    "card": "rgba(17, 24, 39, 0.72)",
    "card_solid": "#111827",
    "border": "rgba(167, 139, 250, 0.18)",
    "border_strong": "rgba(167, 139, 250, 0.35)",
    "text": "#E8EDF7",
    "muted": "#94A3B8",
    "primary": "#A78BFA",
    "primary_2": "#818CF8",
    "cyan": "#38BDF8",
    "green": "#34D399",
    "red": "#F87171",
    "pink": "#F472B6",
    "glow": "rgba(167, 139, 250, 0.35)",
}

_CSS = f"""
<style>
/* ========== Global shell ========== */
.stApp {{
  background:
    radial-gradient(1200px 600px at 10% -10%, rgba(129, 140, 248, 0.18), transparent 55%),
    radial-gradient(900px 500px at 90% 0%, rgba(167, 139, 250, 0.16), transparent 50%),
    radial-gradient(800px 500px at 50% 100%, rgba(56, 189, 248, 0.08), transparent 55%),
    linear-gradient(180deg, #050812 0%, {COLORS['bg']} 40%, #050812 100%) !important;
  color: {COLORS['text']};
}}

[data-testid="stHeader"] {{
  background: rgba(5, 8, 18, 0.55) !important;
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(36, 48, 68, 0.6);
}}

[data-testid="stToolbar"] {{
  background: transparent !important;
}}

/* Sidebar — mesma base do logo TD (#080714) para blend */
[data-testid="stSidebar"] {{
  background: #080714 !important;
  background-color: #080714 !important;
  border-right: 1px solid rgba(167, 139, 250, 0.10) !important;
}}

[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"],
[data-testid="stSidebarUserContent"] {{
  background: #080714 !important;
}}

/* Esconde logo nativo pequeno se aparecer */
[data-testid="stSidebarHeader"],
[data-testid="stLogo"],
[data-testid="stSidebar"] [data-testid="stLogoLink"] {{
  display: none !important;
  height: 0 !important;
  min-height: 0 !important;
  overflow: hidden !important;
  padding: 0 !important;
  margin: 0 !important;
}}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
  color: {COLORS['muted']};
}}

section[data-testid="stSidebar"] .stButton > button {{
  border-radius: 12px;
}}

/* ========== Nav lateral estilo botões (st.navigation) ========== */
[data-testid="stSidebarNav"] {{
  padding: 0.35rem 0.55rem 0.75rem 0.55rem !important;
}}

[data-testid="stSidebarNav"] ul {{
  gap: 0.4rem !important;
  padding: 0 !important;
}}

[data-testid="stSidebarNav"] li {{
  margin: 0 !important;
}}

[data-testid="stSidebarNav"] a,
[data-testid="stSidebarNavLink"] {{
  display: flex !important;
  align-items: center !important;
  gap: 0.65rem !important;
  border-radius: 14px !important;
  padding: 0.72rem 0.9rem !important;
  margin: 0 !important;
  background: linear-gradient(145deg, rgba(17, 24, 39, 0.9), rgba(15, 23, 42, 0.65)) !important;
  border: 1px solid rgba(167, 139, 250, 0.14) !important;
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.22) !important;
  color: #E2E8F0 !important;
  font-weight: 600 !important;
  letter-spacing: -0.01em !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease,
    background 0.15s ease !important;
}}

[data-testid="stSidebarNav"] a:hover,
[data-testid="stSidebarNavLink"]:hover {{
  border-color: rgba(167, 139, 250, 0.4) !important;
  box-shadow: 0 10px 28px rgba(99, 102, 241, 0.18) !important;
  transform: translateY(-1px);
  background: linear-gradient(145deg, rgba(49, 46, 129, 0.45), rgba(15, 23, 42, 0.85)) !important;
}}

[data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stSidebarNavLink"][aria-selected="true"],
[data-testid="stSidebarNavLink"][aria-current="page"] {{
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.42), rgba(59, 130, 246, 0.28)) !important;
  border-color: rgba(167, 139, 250, 0.5) !important;
  box-shadow: 0 0 0 1px rgba(167, 139, 250, 0.15) inset,
    0 12px 30px rgba(99, 102, 241, 0.28) !important;
  color: #F8FAFC !important;
}}

[data-testid="stSidebarNav"] span {{
  font-size: 0.92rem !important;
}}

/* esconde o header default feio da nav se existir */
[data-testid="stSidebarNavSeparator"] {{
  display: none !important;
}}

/* Main content — evita corte sob a barra superior do Streamlit */
.block-container {{
  padding-top: 4.75rem !important;
  padding-bottom: 3.5rem !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
  max-width: 1280px;
}}

/* header fixo não deve cobrir o conteúdo */
[data-testid="stHeader"] {{
  z-index: 999;
  height: 3.25rem;
}}

header[data-testid="stHeader"] {{
  background: rgba(5, 8, 18, 0.72) !important;
}}

/* empurrão extra no 1º bloco da página */
section.main > div {{
  padding-top: 0.25rem;
}}

.td-chart-card {{
  background: linear-gradient(160deg, rgba(17, 24, 39, 0.92), rgba(15, 23, 42, 0.78));
  border: 1px solid rgba(167, 139, 250, 0.16);
  border-radius: 20px;
  padding: 0.55rem 0.55rem 0.35rem 0.55rem;
  box-shadow: 0 14px 40px rgba(0,0,0,0.3);
  margin-bottom: 0.75rem;
  min-height: 100%;
}}

.td-page-title {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  margin: 0 0 1rem 0;
  padding-top: 0.15rem;
}}

.td-page-title h2 {{
  margin: 0 !important;
  font-size: 1.45rem !important;
  font-weight: 700 !important;
  letter-spacing: -0.02em;
  color: #F8FAFC !important;
  background: none !important;
  -webkit-text-fill-color: #F8FAFC !important;
}}

.td-page-title span {{
  color: #94A3B8;
  font-size: 0.88rem;
}}

/* ========== Typography polish ========== */
h1, h2, h3 {{
  letter-spacing: -0.02em !important;
}}

h1 {{
  background: linear-gradient(105deg, #F8FAFC 0%, #C4B5FD 45%, #38BDF8 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent !important;
}}

/* ========== Metrics as glass KPI cards ========== */
[data-testid="stMetric"] {{
  background: linear-gradient(145deg, rgba(17, 24, 39, 0.9), rgba(15, 23, 42, 0.75));
  border: 1px solid {COLORS['border']};
  border-radius: 18px;
  padding: 1rem 1.1rem 0.85rem 1.1rem;
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.02) inset,
    0 12px 40px rgba(0, 0, 0, 0.35),
    0 0 40px rgba(167, 139, 250, 0.05);
  transition: border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}}

[data-testid="stMetric"]:hover {{
  border-color: {COLORS['border_strong']};
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.03) inset,
    0 16px 48px rgba(0, 0, 0, 0.4),
    0 0 50px rgba(167, 139, 250, 0.12);
  transform: translateY(-1px);
}}

[data-testid="stMetric"] label {{
  color: {COLORS['muted']} !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}}

[data-testid="stMetricValue"] {{
  font-size: 1.55rem !important;
  font-weight: 700 !important;
  color: {COLORS['text']} !important;
}}

[data-testid="stMetricDelta"] {{
  font-weight: 600 !important;
}}

/* ========== Header Badges & Chips ========== */
.td-header-badges {{
  display: inline-flex;
  gap: 0.45rem;
  align-items: center;
  margin-left: 0.6rem;
  vertical-align: middle;
}}
.td-badge {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.18rem 0.55rem;
  border-radius: 9999px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}}
.td-badge-live {{
  background: rgba(52, 211, 153, 0.15);
  color: #34D399;
  border: 1px solid rgba(52, 211, 153, 0.35);
}}
.td-badge-demo {{
  background: rgba(167, 139, 250, 0.15);
  color: #C4B5FD;
  border: 1px solid rgba(167, 139, 250, 0.35);
}}
.td-badge-pit {{
  background: rgba(56, 189, 248, 0.15);
  color: #38BDF8;
  border: 1px solid rgba(56, 189, 248, 0.35);
}}
.td-badge-warn {{
  background: rgba(251, 191, 36, 0.15);
  color: #FBBF24;
  border: 1px solid rgba(251, 191, 36, 0.35);
}}

/* ========== Buttons ========== */
.stButton > button {{
  border-radius: 12px !important;
  font-weight: 600 !important;
  border: 1px solid rgba(167, 139, 250, 0.25) !important;
  transition: all 0.18s ease !important;
}}

.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {{
  background: linear-gradient(135deg, #8B5CF6 0%, #6366F1 50%, #3B82F6 100%) !important;
  border: none !important;
  color: white !important;
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.35);
}}

.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {{
  box-shadow: 0 10px 30px rgba(139, 92, 246, 0.5);
  filter: brightness(1.06);
}}

.stButton > button[kind="secondary"] {{
  background: rgba(15, 23, 42, 0.8) !important;
}}

/* ========== Inputs / widgets ========== */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-baseweb="select"] > div,
[data-testid="stDateInput"] input {{
  border-radius: 12px !important;
  background: rgba(15, 23, 42, 0.85) !important;
  border-color: rgba(36, 48, 68, 0.9) !important;
}}

/* Tabs — pill/underline hybrid */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  gap: 0.4rem;
  background: rgba(15, 23, 42, 0.55);
  padding: 0.35rem;
  border-radius: 14px;
  border: 1px solid rgba(36, 48, 68, 0.8);
}}

[data-testid="stTabs"] [data-baseweb="tab"] {{
  border-radius: 10px !important;
  padding: 0.45rem 0.9rem !important;
  color: {COLORS['muted']} !important;
}}

[data-testid="stTabs"] [aria-selected="true"] {{
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.35), rgba(59, 130, 246, 0.25)) !important;
  color: {COLORS['text']} !important;
}}

/* Dataframes */
[data-testid="stDataFrame"],
[data-testid="stDataFrameResizable"] {{
  border: 1px solid {COLORS['border']} !important;
  border-radius: 16px !important;
  overflow: hidden;
  box-shadow: 0 10px 36px rgba(0,0,0,0.28);
}}

/* Expanders / bordered containers feel like cards */
[data-testid="stExpander"] {{
  background: rgba(17, 24, 39, 0.55) !important;
  border: 1px solid {COLORS['border']} !important;
  border-radius: 16px !important;
}}

div[data-testid="stVerticalBlockBorderWrapper"] {{
  background: linear-gradient(160deg, rgba(17, 24, 39, 0.88), rgba(15, 23, 42, 0.72)) !important;
  border: 1px solid {COLORS['border']} !important;
  border-radius: 18px !important;
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.02) inset,
    0 14px 40px rgba(0, 0, 0, 0.28);
  padding: 0.25rem 0.15rem;
}}

/* Alerts softer */
[data-testid="stAlert"] {{
  border-radius: 14px !important;
  border: 1px solid rgba(167, 139, 250, 0.15) !important;
  background: rgba(15, 23, 42, 0.75) !important;
}}

/* Plotly chart container */
[data-testid="stPlotlyChart"] {{
  border-radius: 16px;
  border: 1px solid {COLORS['border']};
  background: rgba(17, 24, 39, 0.55);
  padding: 0.35rem;
  box-shadow: 0 12px 36px rgba(0,0,0,0.25);
}}

/* Forms */
[data-testid="stForm"] {{
  background: rgba(17, 24, 39, 0.5);
  border: 1px solid {COLORS['border']};
  border-radius: 18px;
  padding: 0.75rem 1rem 1rem 1rem;
}}

/* ========== Custom components ========== */
.td-hero {{
  position: relative;
  overflow: hidden;
  border-radius: 24px;
  padding: 1.5rem 1.7rem 1.4rem 1.7rem;
  margin: 0.25rem 0 1rem 0;
  background:
    linear-gradient(125deg, rgba(99, 102, 241, 0.22) 0%, rgba(15, 23, 42, 0.92) 42%, rgba(8, 12, 24, 0.95) 100%);
  border: 1px solid rgba(167, 139, 250, 0.28);
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.03) inset,
    0 20px 60px rgba(0, 0, 0, 0.45),
    0 0 80px rgba(129, 140, 248, 0.12);
}}

.td-hero::before {{
  content: "";
  position: absolute;
  width: 280px;
  height: 280px;
  right: -40px;
  top: -80px;
  background: radial-gradient(circle, rgba(167, 139, 250, 0.35), transparent 70%);
  pointer-events: none;
}}

.td-hero::after {{
  content: "";
  position: absolute;
  width: 220px;
  height: 220px;
  left: 35%;
  bottom: -100px;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.18), transparent 70%);
  pointer-events: none;
}}

.td-hero-kicker {{
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #C4B5FD;
  background: rgba(139, 92, 246, 0.15);
  border: 1px solid rgba(167, 139, 250, 0.3);
  border-radius: 999px;
  padding: 0.28rem 0.7rem;
  margin-bottom: 0.85rem;
}}

.td-hero h1 {{
  margin: 0 0 0.55rem 0 !important;
  font-size: 2.05rem !important;
  line-height: 1.15 !important;
  background: linear-gradient(100deg, #FFFFFF 0%, #DDD6FE 50%, #7DD3FC 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent !important;
  position: relative;
  z-index: 1;
}}

.td-hero p {{
  margin: 0;
  max-width: 46rem;
  color: #CBD5E1;
  font-size: 1.02rem;
  line-height: 1.55;
  position: relative;
  z-index: 1;
}}

.td-hero-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1.1rem;
  position: relative;
  z-index: 1;
}}

.td-chip {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
  font-weight: 500;
  color: #E2E8F0;
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 999px;
  padding: 0.32rem 0.75rem;
}}

.td-chip strong {{
  color: #C4B5FD;
  font-weight: 600;
}}

.td-section-label {{
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #A78BFA;
  margin: 0.4rem 0 0.65rem 0;
}}

.td-feature-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
  margin: 0.25rem 0 1.25rem 0;
}}

@media (max-width: 900px) {{
  .td-feature-grid {{ grid-template-columns: 1fr; }}
}}

.td-feature {{
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  padding: 1.15rem 1.2rem 1.2rem 1.2rem;
  background: linear-gradient(160deg, rgba(17, 24, 39, 0.95), rgba(15, 23, 42, 0.8));
  border: 1px solid {COLORS['border']};
  box-shadow: 0 14px 40px rgba(0,0,0,0.3);
  min-height: 150px;
}}

.td-feature::before {{
  content: "";
  position: absolute;
  inset: 0 auto auto 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, #A78BFA, #38BDF8, transparent);
  opacity: 0.85;
}}

.td-feature-icon {{
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.75rem;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.35), rgba(56, 189, 248, 0.2));
  border: 1px solid rgba(167, 139, 250, 0.3);
  font-size: 1.15rem;
}}

.td-feature h3 {{
  margin: 0 0 0.4rem 0 !important;
  font-size: 1.05rem !important;
  color: #F1F5F9 !important;
  background: none !important;
  -webkit-text-fill-color: #F1F5F9 !important;
}}

.td-feature p {{
  margin: 0;
  color: #94A3B8;
  font-size: 0.9rem;
  line-height: 1.5;
}}

.td-step-card {{
  border-radius: 18px;
  padding: 1.2rem 1.35rem;
  background: linear-gradient(145deg, rgba(30, 27, 75, 0.45), rgba(15, 23, 42, 0.85));
  border: 1px solid rgba(167, 139, 250, 0.22);
  box-shadow: 0 12px 36px rgba(0,0,0,0.28);
  margin-bottom: 1rem;
}}

.td-step-card ol {{
  margin: 0.4rem 0 0 1.1rem;
  padding: 0;
  color: #CBD5E1;
}}

.td-step-card li {{
  margin: 0.35rem 0;
  line-height: 1.45;
}}

.td-kpi-row {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0.85rem;
  margin: 0.4rem 0 1.1rem 0;
}}

.td-kpi {{
  border-radius: 16px;
  padding: 0.95rem 1rem;
  background: linear-gradient(155deg, rgba(17,24,39,0.95), rgba(15,23,42,0.75));
  border: 1px solid {COLORS['border']};
  box-shadow: 0 10px 30px rgba(0,0,0,0.28);
}}

.td-kpi .label {{
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: {COLORS['muted']};
  font-weight: 600;
  margin-bottom: 0.35rem;
}}

.td-kpi .value {{
  font-size: 1.35rem;
  font-weight: 700;
  color: {COLORS['text']};
  line-height: 1.2;
}}

.td-kpi .hint {{
  margin-top: 0.25rem;
  font-size: 0.78rem;
  font-weight: 600;
}}

.td-kpi .hint.up {{ color: {COLORS['green']}; }}
.td-kpi .hint.down {{ color: {COLORS['red']}; }}
.td-kpi .hint.neutral {{ color: {COLORS['muted']}; }}

.td-brand {{
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.35rem 0 0.85rem 0;
  border-bottom: 1px solid rgba(167, 139, 250, 0.12);
  margin-bottom: 0.85rem;
}}

.td-brand-mark {{
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: linear-gradient(135deg, #8B5CF6, #3B82F6);
  box-shadow: 0 8px 20px rgba(139, 92, 246, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  color: white;
  font-size: 0.95rem;
}}

.td-brand-text {{
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}}

.td-brand-text strong {{
  color: #F8FAFC;
  font-size: 0.98rem;
  letter-spacing: -0.01em;
}}

.td-brand-text span {{
  color: #94A3B8;
  font-size: 0.75rem;
}}

.td-guide {{
  border-radius: 16px;
  padding: 1rem 1.15rem;
  margin: 0.5rem 0 1rem 0;
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(56, 189, 248, 0.18);
  box-shadow: 0 10px 28px rgba(0,0,0,0.22);
}}

.td-guide-title {{
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #38BDF8;
  margin-bottom: 0.45rem;
}}

.td-guide ol {{
  margin: 0 0 0 1.05rem;
  padding: 0;
  color: #CBD5E1;
}}

.td-guide li {{ margin: 0.28rem 0; }}

.td-disclaimer {{
  display: flex;
  gap: 0.55rem;
  align-items: flex-start;
  font-size: 0.82rem;
  color: #94A3B8;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 12px;
  padding: 0.65rem 0.85rem;
  margin: 0.35rem 0 1rem 0;
}}

.td-disclaimer span.icon {{ color: #A78BFA; }}

/* ========== Wallet balance (Exodus-style) ========== */
.td-wallet {{
  position: relative;
  overflow: hidden;
  border-radius: 24px;
  padding: 1.5rem 1.6rem 1.35rem 1.6rem;
  margin: 0 0 1.25rem 0;
  background:
    linear-gradient(135deg, rgba(91, 33, 182, 0.55) 0%, rgba(30, 27, 75, 0.9) 38%, rgba(8, 12, 24, 0.96) 100%);
  border: 1px solid rgba(196, 181, 253, 0.28);
  box-shadow:
    0 0 0 1px rgba(255,255,255,0.04) inset,
    0 22px 60px rgba(0, 0, 0, 0.45),
    0 0 80px rgba(139, 92, 246, 0.18);
}}

.td-wallet::before {{
  content: "";
  position: absolute;
  width: 320px;
  height: 320px;
  right: -60px;
  top: -100px;
  background: radial-gradient(circle, rgba(167, 139, 250, 0.45), transparent 68%);
  pointer-events: none;
}}

.td-wallet::after {{
  content: "";
  position: absolute;
  width: 220px;
  height: 220px;
  left: 20%;
  bottom: -120px;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.2), transparent 70%);
  pointer-events: none;
}}

.td-wallet-top {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  position: relative;
  z-index: 1;
}}

.td-wallet-label {{
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #C4B5FD;
  margin-bottom: 0.45rem;
}}

.td-wallet-balance {{
  font-size: clamp(1.9rem, 4vw, 2.55rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #FFFFFF;
  line-height: 1.1;
  text-shadow: 0 8px 30px rgba(0,0,0,0.35);
}}

.td-wallet-delta {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.55rem;
  font-size: 0.92rem;
  font-weight: 600;
  padding: 0.28rem 0.7rem;
  border-radius: 999px;
  border: 1px solid transparent;
}}

.td-wallet-delta.up {{
  color: #6EE7B7;
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(52, 211, 153, 0.25);
}}

.td-wallet-delta.down {{
  color: #FCA5A5;
  background: rgba(248, 113, 113, 0.12);
  border-color: rgba(248, 113, 113, 0.25);
}}

.td-wallet-badge {{
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #E9D5FF;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(196, 181, 253, 0.25);
  border-radius: 999px;
  padding: 0.35rem 0.75rem;
  white-space: nowrap;
}}

.td-wallet-grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 1.25rem;
  position: relative;
  z-index: 1;
}}

@media (max-width: 900px) {{
  .td-wallet-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}

.td-wallet-stat {{
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px;
  padding: 0.75rem 0.85rem;
  backdrop-filter: blur(8px);
}}

.td-wallet-stat .s-label {{
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #94A3B8;
  font-weight: 600;
  margin-bottom: 0.3rem;
}}

.td-wallet-stat .s-value {{
  font-size: 1.05rem;
  font-weight: 700;
  color: #F1F5F9;
}}

.td-wallet-stat .s-tip {{
  margin-top: 0.28rem;
  font-size: 0.68rem;
  line-height: 1.3;
  color: #94A3B8;
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0;
}}

.td-wallet-hint {{
  margin-top: 0.55rem;
  font-size: 0.82rem;
  line-height: 1.4;
  color: #C4B5FD;
  max-width: 36rem;
  opacity: 0.95;
}}

.td-wallet-delta.neutral {{
  color: #E2E8F0;
  background: rgba(148, 163, 184, 0.12);
  border-color: rgba(148, 163, 184, 0.25);
}}

/* ========== Journey / onboarding steps ========== */
.td-journey {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.55rem;
  margin: 0 0 1.1rem 0;
}}
@media (max-width: 900px) {{
  .td-journey {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
.td-journey-step {{
  border-radius: 14px;
  padding: 0.7rem 0.8rem;
  background: linear-gradient(145deg, rgba(17,24,39,0.92), rgba(15,23,42,0.7));
  border: 1px solid rgba(167, 139, 250, 0.14);
}}
.td-journey-step.done {{
  border-color: rgba(52, 211, 153, 0.35);
  background: linear-gradient(145deg, rgba(6, 78, 59, 0.35), rgba(15,23,42,0.75));
}}
.td-journey-step.current {{
  border-color: rgba(167, 139, 250, 0.55);
  box-shadow: 0 0 0 1px rgba(167, 139, 250, 0.2) inset;
  background: linear-gradient(145deg, rgba(91, 33, 182, 0.35), rgba(15,23,42,0.8));
}}
.td-journey-step .n {{
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #94A3B8;
  margin-bottom: 0.25rem;
}}
.td-journey-step.done .n {{ color: #6EE7B7; }}
.td-journey-step.current .n {{ color: #C4B5FD; }}
.td-journey-step .t {{
  font-size: 0.88rem;
  font-weight: 700;
  color: #F1F5F9;
  line-height: 1.25;
}}
.td-journey-step .d {{
  margin-top: 0.2rem;
  font-size: 0.72rem;
  color: #94A3B8;
  line-height: 1.3;
}}

.td-explain-card {{
  border-radius: 16px;
  padding: 0.95rem 1.05rem;
  margin: 0 0 0.85rem 0;
  background: linear-gradient(145deg, rgba(17,24,39,0.95), rgba(15,23,42,0.78));
  border: 1px solid rgba(167, 139, 250, 0.16);
}}
.td-explain-card h4 {{
  margin: 0 0 0.35rem 0;
  font-size: 0.95rem;
  color: #F8FAFC;
  font-weight: 700;
}}
.td-explain-card p {{
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.45;
  color: #94A3B8;
}}
.td-explain-card .big {{
  margin: 0.35rem 0 0.45rem 0;
  font-size: 1.45rem;
  font-weight: 800;
  color: #FFFFFF;
  letter-spacing: -0.02em;
}}

.td-asset-list {{
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  margin: 0.5rem 0 1rem 0;
}}

.td-asset-row {{
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 0.85rem;
  align-items: center;
  padding: 0.85rem 1rem;
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(17,24,39,0.92), rgba(15,23,42,0.75));
  border: 1px solid rgba(167, 139, 250, 0.14);
  box-shadow: 0 8px 24px rgba(0,0,0,0.22);
  transition: border-color 0.15s ease, transform 0.15s ease;
}}

.td-asset-row:hover {{
  border-color: rgba(167, 139, 250, 0.35);
  transform: translateY(-1px);
}}

.td-asset-avatar {{
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 0.78rem;
  color: white;
  background: linear-gradient(135deg, #8B5CF6, #3B82F6);
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35);
}}

.td-asset-name {{
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
}}

.td-asset-name strong {{
  color: #F8FAFC;
  font-size: 0.95rem;
}}

.td-asset-name span {{
  color: #94A3B8;
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}

.td-asset-mid {{
  text-align: right;
  color: #CBD5E1;
  font-size: 0.88rem;
  font-weight: 600;
}}

.td-asset-mid small {{
  display: block;
  color: #94A3B8;
  font-weight: 500;
  font-size: 0.75rem;
  margin-top: 0.15rem;
}}

.td-asset-right {{
  text-align: right;
  min-width: 5.5rem;
}}

.td-asset-right .mv {{
  color: #F8FAFC;
  font-weight: 700;
  font-size: 0.95rem;
}}

.td-asset-right .pnl {{
  font-size: 0.78rem;
  font-weight: 600;
  margin-top: 0.15rem;
}}

.td-asset-right .pnl.up {{ color: #34D399; }}
.td-asset-right .pnl.down {{ color: #F87171; }}

/* ========== UI/UX 2.0: Cards Interativos, Metas e Sentimento ========== */
.td-card-interactive {{
  background: rgba(17, 24, 39, 0.75);
  border: 1px solid rgba(129, 140, 248, 0.2);
  border-radius: 14px;
  padding: 1.25rem;
  margin-bottom: 1rem;
  transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}}
.td-card-interactive:hover {{
  transform: translateY(-2px);
  border-color: rgba(167, 139, 250, 0.45);
  box-shadow: 0 8px 24px rgba(129, 140, 248, 0.12);
}}

/* Metas de Renda Passiva */
.td-goal-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
  margin: 1rem 0 1.5rem 0;
}}
.td-goal-card {{
  background: linear-gradient(145deg, rgba(17, 24, 39, 0.9), rgba(15, 23, 42, 0.8));
  border: 1px solid rgba(129, 140, 248, 0.22);
  border-radius: 14px;
  padding: 1.15rem;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s ease;
}}
.td-goal-card.active {{
  border-color: rgba(52, 211, 153, 0.6);
  box-shadow: 0 0 20px rgba(52, 211, 153, 0.15);
}}
.td-goal-card.completed {{
  border-color: rgba(56, 189, 248, 0.6);
  background: linear-gradient(145deg, rgba(16, 37, 66, 0.85), rgba(15, 23, 42, 0.8));
}}
.td-goal-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}}
.td-goal-title {{
  font-weight: 700;
  font-size: 0.95rem;
  color: #F8FAFC;
}}
.td-goal-target {{
  font-size: 1.25rem;
  font-weight: 800;
  color: #38BDF8;
  margin-bottom: 0.5rem;
}}
.td-goal-prog-track {{
  background: rgba(30, 41, 59, 0.8);
  border-radius: 999px;
  height: 8px;
  width: 100%;
  overflow: hidden;
  margin: 0.5rem 0;
}}
.td-goal-prog-bar {{
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #818CF8, #34D399);
  transition: width 0.4s ease;
}}
.td-goal-footer {{
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  color: #94A3B8;
  margin-top: 0.4rem;
}}

/* Radar de Notícias & Sentimento */
.td-news-feed {{
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin: 0.75rem 0;
}}
.td-news-item {{
  background: rgba(17, 24, 39, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 0.85rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  text-decoration: none !important;
  transition: all 0.18s ease;
}}
.td-news-item:hover {{
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(129, 140, 248, 0.4);
  transform: translateX(3px);
}}
.td-news-title {{
  color: #F1F5F9;
  font-size: 0.88rem;
  font-weight: 500;
  line-height: 1.35;
}}
.td-news-meta {{
  color: #64748B;
  font-size: 0.75rem;
  margin-top: 0.2rem;
  display: flex;
  gap: 0.5rem;
  align-items: center;
}}
.td-sentiment-pill {{
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  white-space: nowrap;
}}
.td-sentiment-pill.positive {{
  background: rgba(52, 211, 153, 0.15);
  color: #34D399;
  border: 1px solid rgba(52, 211, 153, 0.3);
}}
.td-sentiment-pill.negative {{
  background: rgba(248, 113, 113, 0.15);
  color: #F87171;
  border: 1px solid rgba(248, 113, 113, 0.3);
}}
.td-sentiment-pill.neutral {{
  background: rgba(148, 163, 184, 0.15);
  color: #94A3B8;
  border: 1px solid rgba(148, 163, 184, 0.25);
}}

/* Medidores Visuais de Saúde (Sem Jargões) */
.td-health-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
  margin: 0.75rem 0 1rem 0;
}}
.td-health-card {{
  background: rgba(17, 24, 39, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  transition: all 0.2s ease;
}}
.td-health-card:hover {{
  transform: translateY(-2px);
  border-color: rgba(129, 140, 248, 0.35);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}}
.td-health-label {{
  font-size: 0.75rem;
  color: #94A3B8;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}
.td-health-status {{
  font-size: 0.95rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}}
.td-health-status.good {{ color: #34D399; }}
.td-health-status.warn {{ color: #FBBF24; }}
.td-health-status.alert {{ color: #F87171; }}
.td-health-status.neutral {{ color: #94A3B8; }}
.td-health-desc {{
  font-size: 0.78rem;
  color: #94A3B8;
  line-height: 1.3;
}}
.td-health-meter {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.35rem 0.65rem;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.06);
}}

/* Animações Modernas & Transições Fluidas */
@keyframes tdFadeInUp {{
  0% {{
    opacity: 0;
    transform: translateY(12px);
  }}
  100% {{
    opacity: 1;
    transform: translateY(0);
  }}
}}

@keyframes tdPulseGlow {{
  0%, 100% {{
    box-shadow: 0 0 15px rgba(129, 140, 248, 0.2);
  }}
  50% {{
    box-shadow: 0 0 25px rgba(56, 189, 248, 0.35);
  }}
}}

.main .block-container {{
  animation: tdFadeInUp 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}}

.td-hero-glass {{
  background: linear-gradient(135deg, rgba(30, 27, 75, 0.55) 0%, rgba(15, 23, 42, 0.85) 100%);
  border: 1px solid rgba(167, 139, 250, 0.25);
  border-radius: 16px;
  padding: 1.5rem 1.75rem;
  backdrop-filter: blur(16px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08);
  margin-bottom: 1.25rem;
  animation: tdFadeInUp 0.3s ease-out;
}}

.td-quick-actions-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin: 1.25rem 0;
}}

.td-quick-card {{
  background: rgba(17, 24, 39, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}}
.td-quick-card:hover {{
  transform: translateY(-3px);
  border-color: rgba(129, 140, 248, 0.45);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.35), 0 0 15px rgba(129, 140, 248, 0.15);
}}

/* Microinterações de Botões e Métricas */
.stButton > button {{
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
  font-weight: 600 !important;
}}
.stButton > button:hover {{
  transform: translateY(-1.5px) !important;
  box-shadow: 0 6px 20px rgba(129, 140, 248, 0.25) !important;
}}
.stButton > button:active {{
  transform: translateY(0px) !important;
}}

[data-testid="stMetric"] {{
  background: rgba(17, 24, 39, 0.7) !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 14px !important;
  padding: 0.85rem 1rem !important;
  transition: all 0.2s ease !important;
}}
[data-testid="stMetric"]:hover {{
  border-color: rgba(129, 140, 248, 0.35) !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.25) !important;
}}

[data-testid="stExpander"] {{
  border-radius: 12px !important;
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  background: rgba(17, 24, 39, 0.6) !important;
  backdrop-filter: blur(12px) !important;
  transition: border-color 0.2s ease !important;
}}
[data-testid="stExpander"]:hover {{
  border-color: rgba(129, 140, 248, 0.3) !important;
}}
</style>

"""




def apply_theme() -> None:
    """Injeta o visual dark fintech. Seguro chamar em toda página."""
    st.markdown(_CSS, unsafe_allow_html=True)
