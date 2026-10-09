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


_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def dia_semana_es(fecha) -> str:
    """'lunes', 'martes'… sin depender del locale del sistema (Windows/Railway)."""
    return _DIAS_ES[fecha.weekday()]


def fecha_larga_es(fecha: datetime | None = None, con_hora: bool = True, sep: str = " · ") -> str:
    """'Viernes 09 de octubre de 2026 · 16:28' en español, independiente del locale."""
    f = fecha or ahora_bogota()
    texto = f"{dia_semana_es(f).capitalize()} {f.day:02d} de {_MESES_ES[f.month - 1]} de {f.year}"
    return f"{texto}{sep}{f:%H:%M}" if con_hora else texto
