"""Estilos CSS personalizados para el dashboard Streamlit."""

CSS = """
<style>
    .main { padding: 1rem 1.5rem; }
    .stMetric { background: #f8f9fa; border-radius: 10px; padding: 1rem; border: 1px solid #e9ecef; }
    .chat-msg-user { background: #EEEDFE; border-radius: 12px 2px 12px 12px; padding: 10px 14px; margin: 4px 0; color: #26215C; font-size: 14px; }
    .chat-msg-agent { background: #f8f9fa; border-radius: 2px 12px 12px 12px; padding: 10px 14px; margin: 4px 0; border: 1px solid #e9ecef; font-size: 14px; }
    .alert-critico { background: #FCEBEB; border-left: 4px solid #E24B4A; padding: 8px 12px; border-radius: 0 6px 6px 0; margin: 4px 0; }
    .alert-urgente { background: #FAEEDA; border-left: 4px solid #BA7517; padding: 8px 12px; border-radius: 0 6px 6px 0; margin: 4px 0; }
    .alert-aviso { background: #E6F1FB; border-left: 4px solid #185FA5; padding: 8px 12px; border-radius: 0 6px 6px 0; margin: 4px 0; }
    div[data-testid="stSidebar"] { background: #fafafa; }
    .status-active { color: #27500A; font-weight: 500; }
    .section-title { font-size: 13px; font-weight: 600; color: #6c757d; text-transform: uppercase; letter-spacing: 0.5px; margin: 1rem 0 0.5rem; }
</style>
"""
