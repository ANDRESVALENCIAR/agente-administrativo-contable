"""
Configuración central del agente. Lee todas las variables de entorno.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración global del sistema administrativo-contable."""

    # Claude
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    MODELO_SIMPLE = "claude-haiku-4-5-20251001"
    MODELO_COMPLEJO = "claude-sonnet-4-6"

    # Gmail
    GMAIL_USER = os.getenv("GMAIL_USER")
    GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH")
    GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH")

    # Microsoft 365
    MS_CLIENT_ID = os.getenv("MS_CLIENT_ID")
    MS_CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")
    MS_TENANT_ID = os.getenv("MS_TENANT_ID")
    MS_USER_EMAIL = os.getenv("MS_USER_EMAIL")

    # Excel IDs en OneDrive
    EXCEL_IMPUESTOS_ID = os.getenv("EXCEL_IMPUESTOS_ID")
    EXCEL_VENTAS_ID = os.getenv("EXCEL_VENTAS_ID")
    EXCEL_PERSONAL_ID = os.getenv("EXCEL_PERSONAL_ID")
    EXCEL_CXP_CXC_ID = os.getenv("EXCEL_CXP_CXC_ID")
    EXCEL_PRESUPUESTO_ID = os.getenv("EXCEL_PRESUPUESTO_ID")
    EXCEL_CONCILIACION_ID = os.getenv("EXCEL_CONCILIACION_ID")
    EXCEL_CONTRATOS_ID = os.getenv("EXCEL_CONTRATOS_ID")

    # Correos destino
    EMAIL_CONTABILIDAD = os.getenv("EMAIL_CONTABILIDAD")
    EMAIL_SERVICIO = os.getenv("EMAIL_SERVICIO")
    EMAIL_TESORERIA = os.getenv("EMAIL_TESORERIA")
    EMAIL_PAGOS = os.getenv("EMAIL_PAGOS") or os.getenv("EMAIL_TESORERIA")
    EMAIL_COMPRAS = os.getenv("EMAIL_COMPRAS")
    EMAIL_CARTERA = os.getenv("EMAIL_CARTERA")
    EMAIL_GERENCIA = os.getenv("EMAIL_GERENCIA")
    EMAIL_RRHH = os.getenv("EMAIL_RRHH")
    EMAIL_JURIDICO = os.getenv("EMAIL_JURIDICO")
    EMAIL_LEGAL = os.getenv("EMAIL_LEGAL") or os.getenv("EMAIL_JURIDICO")
    EMAIL_ALERTAS = os.getenv("EMAIL_ALERTAS")

    # Empresa
    NOMBRE_EMPRESA = os.getenv("NOMBRE_EMPRESA", "EIF SAS")
    NIT_EMPRESA = os.getenv("NIT_EMPRESA", "900.000.000-0")
    CIUDAD_EMPRESA = os.getenv("CIUDAD_EMPRESA", "Cali")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "agente.db")

    # Destinos de correo por categoría (PROMPT_MAESTRO_SHAKI_v2)
    DESTINOS_CORREO = {
        "factura": os.getenv("EMAIL_CONTABILIDAD"),
        "pqr": os.getenv("EMAIL_SERVICIO"),
        "registro_proveedor": os.getenv("EMAIL_COMPRAS"),
        "solicitud_pago": EMAIL_PAGOS,
        "cobranza": EMAIL_CARTERA,
        "juridico": EMAIL_LEGAL,
        "extracto_bancario": os.getenv("EMAIL_CONTABILIDAD"),
        "comunicacion_interna": os.getenv("EMAIL_GERENCIA"),
        "nomina": os.getenv("EMAIL_RRHH"),
        "incapacidad": os.getenv("EMAIL_RRHH"),
        "otro": os.getenv("EMAIL_GERENCIA"),
        # Alias compatibles con versiones anteriores
        "pago": EMAIL_PAGOS,
        "proveedor": os.getenv("EMAIL_COMPRAS"),
        "comunicacion": os.getenv("EMAIL_GERENCIA"),
    }


cfg = Config()


def en_modo_demo() -> bool:
    """
    Indica si el sistema opera en modo demo (sin credenciales reales).

    Returns:
        True si faltan credenciales críticas o son placeholders.
    """
    clave = cfg.ANTHROPIC_API_KEY or ""
    if not clave or clave.startswith("sk-ant-xxx"):
        return True
    return False


def gmail_configurado() -> bool:
    """True si Gmail tiene credenciales válidas."""
    if en_modo_demo():
        return False
    return bool(
        cfg.GMAIL_USER
        and cfg.GMAIL_CREDENTIALS_PATH
        and os.path.exists(cfg.GMAIL_CREDENTIALS_PATH)
    )


def microsoft_configurado() -> bool:
    """True si Microsoft 365 tiene credenciales válidas."""
    if en_modo_demo():
        return False
    return bool(cfg.MS_CLIENT_ID and cfg.MS_CLIENT_SECRET and cfg.MS_TENANT_ID)
