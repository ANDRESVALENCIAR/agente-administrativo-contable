"""Estilos CSS personalizados para el dashboard Streamlit — tema claro forzado."""

CSS = """
<style>
    :root {
        color-scheme: light only;
    }

    html, body, .stApp {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    .stApp {
        --background-color: #ffffff;
        --secondary-background-color: #ffffff;
        --text-color: #000000;
        --primary-color: #000000;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > section,
    [data-testid="stMain"],
    [data-testid="stMain"] > div,
    .main,
    .main .block-container,
    [data-testid="stHeader"],
    header[data-testid="stHeader"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"],
    [data-testid="stSidebarUserContent"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp p, .stApp span, .stApp label, .stApp li, .stApp a,
    .stMarkdown, .stMarkdown p, .stCaption, .stText,
    [data-testid="stSidebar"] *, [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"], [data-testid="stWidgetLabel"] {
        color: #000000 !important;
    }

    .main { padding: 1rem 1.5rem; }

    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #cccccc !important;
    }

    [data-testid="stMetric"] label,
    [data-testid="stMetric"] [data-testid="stMetricValue"],
    [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: #000000 !important;
    }

    .stButton > button,
    [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-primary"],
    [data-baseweb="button"] {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #000000 !important;
    }

    .stButton > button:hover {
        background-color: #f5f5f5 !important;
        color: #000000 !important;
    }

    .stRadio label,
    .stRadio label span,
    .stRadio [data-baseweb="radio"] {
        color: #000000 !important;
    }

    .stTextInput input,
    .stTextInput textarea {
        background-color: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #cccccc !important;
    }

    .chat-msg-user,
    .chat-msg-agent {
        background: #ffffff !important;
        color: #000000 !important;
        border: 1px solid #cccccc !important;
        padding: 10px 14px;
        margin: 4px 0;
        font-size: 14px;
    }

    .chat-msg-user { border-radius: 12px 2px 12px 12px; }
    .chat-msg-agent { border-radius: 2px 12px 12px 12px; }

    .alert-critico, .alert-urgente, .alert-aviso {
        background: #ffffff !important;
        color: #000000 !important;
        padding: 8px 12px;
        border-radius: 0 6px 6px 0;
        margin: 4px 0;
        border: 1px solid #cccccc !important;
    }

    .alert-critico { border-left: 4px solid #000000 !important; }
    .alert-urgente { border-left: 4px solid #333333 !important; }
    .alert-aviso { border-left: 4px solid #666666 !important; }

    .alert-critico strong, .alert-urgente strong, .alert-aviso strong,
    .alert-critico small, .alert-urgente small, .alert-aviso small {
        color: #000000 !important;
    }

    .status-active { color: #000000 !important; font-weight: 500; }

    .section-title {
        font-size: 13px;
        font-weight: 600;
        color: #000000 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 1rem 0 0.5rem;
    }

    [data-testid="stDataFrame"],
    [data-testid="stTable"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    hr {
        border-color: #e0e0e0 !important;
    }
</style>
"""
