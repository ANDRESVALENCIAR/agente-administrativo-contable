"""Estilos del dashboard — tema "Shaki Black" (grafito, un solo acento para lo urgente)."""

# Paleta (reutilizable desde las páginas)
BG = "#0A0B0D"
SURFACE = "#0F1012"
SURFACE_2 = "#141518"
BORDER = "#1F2024"
BORDER_2 = "#2A2B30"
TEXT = "#E8E8EA"
TEXT_STRONG = "#FFFFFF"
MUTED = "#8B8B93"
MUTED_2 = "#A1A1AA"
ACCENT = "#FF6A3D"
OK = "#4ADE80"

# Plotly: fondo transparente y tipografía del tema
PLOTLY_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Geist, system-ui, sans-serif", color=MUTED_2, size=12),
    margin=dict(l=8, r=8, t=24, b=8),
)

CSS = f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
    :root {{ color-scheme: dark; }}

    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
    [data-testid="stHeader"] {{
        background: {BG} !important;
        color: {TEXT};
    }}
    .stApp, .stApp button, .stApp input, .stApp textarea, .stApp select,
    .stMarkdown, [data-testid="stSidebar"] {{
        font-family: 'Geist', system-ui, -apple-system, sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }}
    [data-testid="stHeader"] {{ background: transparent !important; }}
    [data-testid="stDecoration"] {{ display: none; }}

    .main .block-container, [data-testid="stMainBlockContainer"] {{
        padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1480px;
    }}

    .stApp h1, .stApp h2, .stApp h3 {{
        font-weight: 500 !important; letter-spacing: -0.02em; color: {TEXT_STRONG};
    }}
    .stApp h2 {{ font-size: 1.6rem !important; }}
    .stApp h3 {{ font-size: 1.15rem !important; }}
    .stCaption, [data-testid="stCaptionContainer"] {{ color: {MUTED} !important; }}
    hr {{ border-color: {BORDER} !important; }}

    /* ── Sidebar: navegación tipo lista limpia ── */
    section[data-testid="stSidebar"] {{
        background: {SURFACE} !important;
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 2px; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label {{
        width: 100%; padding: 9px 12px; border-radius: 10px; margin: 0;
        color: {MUTED_2}; transition: background .15s ease, color .15s ease; cursor: pointer;
    }}
    section[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div:not([data-testid="stMarkdownContainer"]) {{ display: none; }}
    section[data-testid="stSidebar"] [data-testid="stRadioOption"] > div {{ gap: 0; }}
    section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{ background: #F4F4F5; }}
    section[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p {{ color: {BG} !important; font-weight: 500; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
        background: #F4F4F5; color: {BG};
    }}
    section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{ color: {BG} !important; font-weight: 500; }}
    section[data-testid="stSidebar"] [role="radiogroup"] label p {{ font-size: 14px; }}

    .sk-brand {{ display: flex; align-items: center; gap: 12px; margin: 4px 0 18px 0; }}
    .sk-logo {{
        width: 32px; height: 32px; border-radius: 9px; background: #F4F4F5;
        display: flex; align-items: center; justify-content: center;
    }}
    .sk-brand-name {{ font-size: 16px; font-weight: 600; color: {TEXT_STRONG}; line-height: 1.1; }}
    .sk-brand-sub {{ font-size: 11px; color: {MUTED}; letter-spacing: .08em; text-transform: uppercase; }}
    .sk-pill {{
        display: inline-flex; align-items: center; gap: 8px; font-size: 12px; color: {MUTED_2};
        padding: 6px 12px; border: 1px solid {BORDER_2}; border-radius: 999px;
    }}
    .sk-dot {{ width: 6px; height: 6px; border-radius: 50%; background: {OK}; display: inline-block; }}
    .sk-urgent {{
        margin-top: 12px; padding: 12px 14px; border-radius: 12px; border: 1px solid {BORDER_2};
        font-size: 13px; color: {MUTED_2};
    }}
    .sk-urgent b {{ color: {ACCENT}; font-weight: 500; font-size: 18px; margin-right: 6px; }}

    /* ── Botones: píldoras ── */
    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {{
        border-radius: 999px !important; border: 1px solid {BORDER_2} !important;
        background: transparent !important; color: {TEXT} !important;
        min-height: 40px; font-weight: 400; transition: all .15s ease;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover,
    [data-testid="stFormSubmitButton"] > button:hover {{
        border-color: #52525B !important; background: {SURFACE_2} !important; color: {TEXT_STRONG} !important;
    }}
    .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button {{
        background: #F4F4F5 !important; color: {BG} !important; border-color: #F4F4F5 !important; font-weight: 500;
    }}
    .stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] > button:hover {{
        background: {TEXT_STRONG} !important; color: {BG} !important;
    }}

    /* ── Entradas ── */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input,
    [data-baseweb="select"] > div {{
        background: {SURFACE_2} !important; border-radius: 12px !important;
        border-color: {BORDER_2} !important; color: {TEXT} !important;
    }}

    /* ── Métricas nativas (resto de páginas) ── */
    [data-testid="stMetric"] {{
        background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 18px; padding: 20px 22px;
    }}
    [data-testid="stMetricLabel"] p {{ color: {MUTED} !important; font-size: 13px !important; }}
    [data-testid="stMetricValue"] {{
        font-weight: 300 !important; letter-spacing: -0.03em; color: {TEXT_STRONG} !important;
    }}

    /* ── Tablas, expanders, tabs, avisos ── */
    [data-testid="stDataFrame"], [data-testid="stTable"] {{
        border: 1px solid {BORDER}; border-radius: 14px; overflow: hidden;
    }}
    [data-testid="stExpander"] details {{ background: {SURFACE}; border: 1px solid {BORDER} !important; border-radius: 14px; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {BORDER}; }}
    .stTabs [data-baseweb="tab"] {{ color: {MUTED_2}; }}
    .stTabs [aria-selected="true"] {{ color: {TEXT_STRONG} !important; }}
    [data-testid="stAlert"] {{ border-radius: 14px; border: 1px solid {BORDER_2}; }}

    /* ── Inicio ── */
    .sk-eyebrow {{ font-size: 12px; color: {MUTED}; letter-spacing: .08em; text-transform: uppercase; }}
    .sk-hero {{ padding: 18px 0 8px 0; }}
    .sk-hero-num {{
        font-size: clamp(48px, 7vw, 96px); line-height: .98; font-weight: 300;
        letter-spacing: -0.045em; color: {TEXT_STRONG}; margin: 14px 0 16px 0;
    }}
    .sk-hero-sub {{ display: flex; flex-wrap: wrap; gap: 26px; font-size: 15px; color: {MUTED_2}; }}
    .sk-hero-sub strong {{ color: {TEXT}; font-weight: 500; }}
    .sk-hero-sub .sk-acc {{ color: {ACCENT}; }}
    .sk-bar {{ display: flex; height: 6px; border-radius: 999px; overflow: hidden; gap: 3px; margin: 28px 0 10px 0; }}
    .sk-legend {{
        display: flex; flex-wrap: wrap; gap: 22px; font-size: 11px; color: {MUTED};
        font-family: 'Geist Mono', monospace; letter-spacing: .04em;
    }}
    .sk-kpis {{
        display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 1px;
        background: {BORDER}; border: 1px solid {BORDER}; border-radius: 20px; overflow: hidden; margin: 34px 0 26px 0;
    }}
    .sk-kpi {{ background: {SURFACE}; padding: 22px 20px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }}
    @media (max-width: 1100px) {{ .sk-kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
    .sk-kpi-l {{ font-size: 13px; color: {MUTED}; }}
    .sk-kpi-v {{ font-size: 40px; font-weight: 300; letter-spacing: -0.03em; color: {TEXT_STRONG}; line-height: 1; }}
    .sk-kpi-f {{ font-size: 11px; color: {MUTED}; font-family: 'Geist Mono', monospace; letter-spacing: .04em; }}
    .sk-card-h {{ display: flex; justify-content: space-between; align-items: baseline; margin: 6px 0 6px 0; }}
    .sk-card-h h4 {{ margin: 0; font-size: 18px; font-weight: 500; color: {TEXT_STRONG}; letter-spacing: -0.01em; }}
    .sk-row {{ display: flex; align-items: center; gap: 14px; padding: 12px 0; border-top: 1px solid {BORDER}; }}
    .sk-row-t {{ font-size: 15px; color: {TEXT}; }}
    .sk-row-s {{ font-size: 13px; color: {MUTED}; margin-top: 3px; }}
    .sk-tag {{
        font-size: 10.5px; font-family: 'Geist Mono', monospace; padding: 3px 8px; border-radius: 6px;
        white-space: nowrap; font-weight: 500; letter-spacing: .03em;
    }}
    .sk-tag-crit {{ background: {ACCENT}; color: {BG}; }}
    .sk-tag-urg {{ background: #F5C542; color: {BG}; }}
    .sk-tag-av {{ border: 1px solid #3F3F46; color: {TEXT}; }}
    .sk-date {{ width: 52px; flex: none; text-align: center; }}
    .sk-date b {{ display: block; font-size: 26px; font-weight: 300; color: {TEXT_STRONG}; line-height: 1.1; }}
    .sk-date span {{ font-size: 11px; color: {MUTED}; font-family: 'Geist Mono', monospace; }}
    .sk-venc {{ color: {ACCENT} !important; }}
    .sk-log {{ font-size: 13px; color: {MUTED}; padding: 6px 0; border-top: 1px solid {BORDER}; }}
    .sk-log b {{ color: {TEXT}; font-weight: 500; }}

    /* Tarjetas de alertas compatibles con otras páginas */
    .alert-critico, .alert-urgente, .alert-aviso {{
        background: {SURFACE}; color: {TEXT}; padding: 12px 14px; border-radius: 12px; margin: 4px 0;
        border: 1px solid {BORDER};
    }}
    .alert-critico strong {{ color: {ACCENT}; }}
    .alert-urgente strong {{ color: #F5C542; }}
    .alert-critico small, .alert-urgente small, .alert-aviso small {{ color: {MUTED}; }}
    .section-title {{
        font-size: 12px; font-weight: 500; color: {MUTED}; text-transform: uppercase;
        letter-spacing: .08em; margin: 1rem 0 .5rem;
    }}
    .status-active {{ color: {MUTED_2}; }}

    /* ── Chat ── */
    .sk-chat-h {{ display: flex; align-items: center; gap: 10px; margin: 6px 0 14px 0; }}
    .sk-chat-h span {{ font-size: 16px; font-weight: 500; color: {TEXT_STRONG}; }}
    .chat-msg-user, .chat-msg-agent {{
        padding: 11px 15px; margin: 6px 0; font-size: 14px; line-height: 1.5; white-space: pre-line;
    }}
    .chat-msg-agent {{
        background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 4px 16px 16px 16px;
    }}
    .chat-msg-user {{
        background: #F4F4F5; color: {BG}; border-radius: 16px 4px 16px 16px; margin-left: 18%;
    }}
    [data-testid="stForm"] {{
        background: rgba(24,25,28,.86); border: 1px solid {BORDER_2} !important; border-radius: 22px;
        padding: 10px 12px; box-shadow: 0 24px 60px rgba(0,0,0,.45);
    }}
    [data-testid="stForm"] .stTextInput input {{ background: transparent !important; border: none !important; font-size: 15px; }}
</style>
"""

LOGO_SVG = (
    '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0A0B0D" '
    'stroke-width="2.4" stroke-linecap="round"><path d="M17 6.5C15.8 5.5 14.2 5 12.4 5 9.4 5 7.5 6.6 '
    '7.5 8.6c0 4.8 9 2.6 9 7.2 0 2-2 3.4-4.8 3.4-2 0-3.8-.7-5.2-2"></path></svg>'
)
