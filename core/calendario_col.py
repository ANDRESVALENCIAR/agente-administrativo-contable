"""Calendario laboral Colombia — festivos y días hábiles."""
from datetime import date, timedelta

try:
    import holidays

    _CO = holidays.Colombia()
    _HAS = True
except ImportError:
    _CO = None
    _HAS = False


def es_festivo_colombia(fecha: date | None = None) -> bool:
    """True si la fecha es festivo en Colombia."""
    if not _HAS:
        return False
    from core.registro_libs import registrar_uso_libreria

    registrar_uso_libreria("personal", "holidays")
    d = fecha or date.today()
    return d in _CO


def es_dia_habil(fecha: date | None = None) -> bool:
    """True si es día laborable (lun–vie, no festivo)."""
    d = fecha or date.today()
    if d.weekday() >= 5:
        return False
    return not es_festivo_colombia(d)


def proximo_dia_habil(fecha: date | None = None) -> date:
    """Siguiente día hábil desde fecha dada."""
    d = (fecha or date.today()) + timedelta(days=1)
    while not es_dia_habil(d):
        d += timedelta(days=1)
    return d
