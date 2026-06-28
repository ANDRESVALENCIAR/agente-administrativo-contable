"""Formato colombiano: pesos y números en letras."""
from datetime import datetime

try:
    from babel.numbers import format_currency

    _HAS_BABEL = True
except ImportError:
    _HAS_BABEL = False

try:
    from num2words import num2words

    _HAS_NUM2WORDS = True
except ImportError:
    _HAS_NUM2WORDS = False

try:
    import pytz

    TZ_BOGOTA = pytz.timezone("America/Bogota")
except ImportError:
    TZ_BOGOTA = None


def valor_pesos(monto: float) -> str:
    """Formatea monto en pesos colombianos."""
    if _HAS_BABEL:
        from core.registro_libs import registrar_uso_libreria

        registrar_uso_libreria("contabilidad", "babel")
        return format_currency(monto, "COP", locale="es_CO")
    return f"${monto:,.0f} COP"


def numero_a_letras(numero: float, idioma: str = "es") -> str:
    """Convierte número a palabras (contratos, certificaciones)."""
    if _HAS_NUM2WORDS:
        from core.registro_libs import registrar_uso_libreria

        registrar_uso_libreria("personal", "num2words")
        entero = int(round(numero))
        return num2words(entero, lang=idioma)
    return str(int(round(numero)))


def ahora_bogota() -> datetime:
    """Datetime en zona horaria Bogotá."""
    if TZ_BOGOTA:
        from core.registro_libs import registrar_uso_libreria

        registrar_uso_libreria("agente", "pytz")
        return datetime.now(TZ_BOGOTA)
    return datetime.now()
