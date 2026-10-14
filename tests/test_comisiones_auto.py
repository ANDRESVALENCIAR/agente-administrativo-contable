"""Liquidación automática de comisiones: correo con RECAUDO_VIA + RECAUDO_CONTABILIDAD y orden «liquidar comisiones»."""
import os
import sys
from datetime import datetime
from email.message import EmailMessage
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl  # noqa: E402
import pytest  # noqa: E402

from config import cfg  # noqa: E402


def _xlsx(filas):
    wb = openpyxl.Workbook()
    for f in filas:
        wb.active.append(f)
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


VIA = _xlsx([
    ["entro aqui"],
    ["Item", "(1) #sfe", "(2) Fecha", "(5) NIT", "(6) Empresa", "(17) Asesor", "Abono", "Abono", "Abono"],
    [1, 22001, "2026-09-01", 900, "CLIENTE UNO", "MCV", 100, None, None],
    [2, 22002, "2026-09-02", 901, "CLIENTE DOS", "EGP", 50, 25, None],
    [3, 22003, "2026-09-03", 902, "CLIENTE TRES", "EGP", None, None, None],
])
CONT = _xlsx([
    ["Vendedor", "Tercero", "Cuenta", "Fecha", "Nota", "Doc Num", "Saldo"],
    ["ANA PEREZ", "CLIENTE UNO", "1120", "2026-09-05", "PAGO SFE 22001 RC 1", "RC 31", 1000],
    ["ANA PEREZ", "CLIENTE DOS", "1120", "2026-09-06", "PAGO SFE 22002 RC 2", "RC 32", 500],
    ["Total ANA PEREZ", None, None, None, None, None, 1500],
    ["LUIS GOMEZ", "OTRO", "1120", "2026-09-07", "RC 3", "RC 33", 200],
    ["Total general", None, None, None, None, None, 1700],
])


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(cfg, "DATABASE_PATH", str(db))
    monkeypatch.setattr(cfg, "COMISIONES_ENTRADA", str(tmp_path / "entrada"))
    monkeypatch.setattr(cfg, "COMISIONES_AVISO_EMAILS", "")
    monkeypatch.setattr(cfg, "PAGOS_ALERTA_EMAILS", "")
    monkeypatch.setattr(cfg, "EMAIL_GERENCIA", "")
    monkeypatch.setattr(cfg, "COMISIONES_DOMINIOS", "viaindustrial.com")
    import modulos.comparador_comisiones as cmp
    monkeypatch.setattr(cmp, "carpeta_comisiones", lambda: (tmp_path / "com").mkdir(exist_ok=True) or tmp_path / "com")
    from database import inicializar_db
    inicializar_db()
    from modulos import comisiones_auto as ca
    monkeypatch.setattr("conexiones.notificador.enviar_email", lambda *a, **k: True)
    return ca


def _correo(asunto, adjuntos=()):
    m = EmailMessage()
    m["From"] = "conta@viaindustrial.com"
    m["Subject"] = asunto
    m["Message-ID"] = f"<{asunto}@t>"
    m.set_content("hola")
    for nombre, data in adjuntos:
        m.add_attachment(data, maintype="application", subtype="octet-stream", filename=nombre)
    return m


def test_periodo_y_tipo():
    from modulos import comisiones_auto as ca
    assert ca.periodo_de("RECAUDO_VIA_SEPTIEMBRE_2026.xlsx") == "2026-09"
    assert ca.tipo_archivo("RECAUDO_CONTABILIDAD_SEPTIEMBRE_2026.xlsx") == "cont"
    assert ca.tipo_archivo("RECAUDO_VIA_SEPTIEMBRE_2026.xlsx") == "via"
    assert ca.tipo_archivo("factura.pdf") is None
    assert ca.es_orden_liquidar("Liquidar comisiones") and not ca.es_orden_liquidar("Comisiones de septiembre")


def test_correo_liquida_una_sola_vez(entorno):
    ca = entorno
    from modulos import buzones
    archivos = [("RECAUDO_VIA_SEPTIEMBRE_2026.xlsx", VIA), ("RECAUDO_CONTABILIDAD_SEPTIEMBRE_2026.xlsx", CONT)]
    m1 = _correo("Recaudos de septiembre", archivos)
    buzones._comisiones_desde_correo(m1, "conta@viaindustrial.com", m1["Subject"], "", datetime(2026, 10, 14))
    assert ca.procesar_pendientes() == []                       # sin la orden no liquida
    m2 = _correo("Liquidar comisiones")
    buzones._comisiones_desde_correo(m2, "conta@viaindustrial.com", "Liquidar comisiones", "", datetime(2026, 10, 14))
    r = ca.procesar_pendientes()
    assert r[0]["estado"] == "liquidado" and r[0]["mensaje"].startswith("Ya liquidé las comisiones de septiembre 2026")
    res = r[0]["resumen"]
    assert res["recaudo_total"] == 1700 and res["recibos"] == 3 and res["coincidencias"] == 2 and res["solo_via"] == 1
    assert res["sin_sfe"] == 1 and "enviado" in r[0]["aviso"]
    # mismos archivos y otra orden: no repite
    buzones._comisiones_desde_correo(m1, "conta@viaindustrial.com", m1["Subject"], "", datetime(2026, 10, 14))
    ca.registrar_orden("conta@viaindustrial.com", "liquidar comisiones", "otra")
    assert ca.procesar_pendientes()[0]["estado"] == "repetido"


def test_faltan_archivos_y_remitente_externo(entorno):
    ca = entorno
    from modulos import buzones
    m = _correo("Liquidar comisiones", [("RECAUDO_VIA_SEPTIEMBRE_2026.xlsx", VIA)])
    buzones._comisiones_desde_correo(m, "conta@viaindustrial.com", "Liquidar comisiones", "", datetime(2026, 10, 14))
    r = ca.procesar_pendientes()
    assert r[0]["estado"] == "faltan_archivos" and "contabilidad" in r[0]["mensaje"]
    assert not ca.remitente_autorizado("alguien@gmail.com")
    assert ca.remitente_autorizado("sandra@viaindustrial.com")
