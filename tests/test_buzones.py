"""Buzones: clasificación de correos colombianos, bandeja y alertas por categoría (sin red)."""
import os
import sys
import tempfile
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.mkdtemp(), "buz.db"))

import pytest  # noqa: E402

from config import cfg  # noqa: E402
from database import inicializar_db  # noqa: E402
from modulos import buzones as bz  # noqa: E402


@pytest.fixture(autouse=True)
def _bd(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "DATABASE_PATH", str(tmp_path / "buz.db"))
    inicializar_db()


@pytest.mark.parametrize("rem,asunto,cuerpo,adj,esperado", [
    ("notificaciones@cendoj.ramajudicial.gov.co", "Notificación auto", "Juzgado 12 civil", [], "JUDICIAL"),
    ("x@empresa.com", "Embargo de cuentas", "", [], "JUDICIAL"),
    ("notificacionesrut@dian.gov.co", "Requerimiento ordinario 2026", "", [], "DIAN"),
    ("facturacion@dian.gov.co", "Documento validado por la DIAN", "Factura validada", [], "DIAN_INFO"),
    ("notificaciones@haciendabogota.gov.co", "Cobro coactivo predial", "", [], "HACIENDA"),
    ("facturas@proveedor.com", "900123456;PROVEEDOR SAS;FE-1234;01;EQUIPOS INDUSTRIALES FENIX", "", ["fe.zip"], "FACTURA"),
    ("cartera@cliente.com", "Cuenta de cobro septiembre", "saldo pendiente de pago", [], "COBRO"),
    ("alertas@bancolombia.com.co", "Transferencia exitosa", "", [], "BANCO"),
    ("alertas@bancolombia.com.co", "Pago rechazado", "fondos insuficientes", [], "BANCO_PROBLEMA"),
    ("compras@cliente.com", "Solicitud de cotización manómetros", "Buen día, nos cotizan?", [], "COTIZACION"),
    ("news@tienda.com", "Black Friday", "unsubscribe", [], "PUBLICIDAD"),
    ("juan@x.com", "Hola", "Nos vemos mañana", [], "OTRO"),
])
def test_clasificar(rem, asunto, cuerpo, adj, esperado):
    assert bz.clasificar(rem, asunto, cuerpo, adj)[0] == esperado


def test_sembrado_y_clave(monkeypatch):
    bz.inicializar()
    emails = [b["email"] for b in bz.listar_buzones()]
    assert set(bz.BUZONES_INICIALES) <= set(emails)
    assert bz.servidor_para("gerencia@viaindustrial.com") == ("mail.viaindustrial.com", 993)
    assert bz.env_clave("gerencia@viaindustrial.com") == "CORREO_PASS_GERENCIA_VIAINDUSTRIAL_COM"
    b = bz.listar_buzones()[0]
    assert b["estado"] == "FALTA CONTRASEÑA"
    monkeypatch.setenv(bz.env_clave(b["email"]), "x")
    assert bz.tiene_clave(b["email"])


def test_bandeja_alertas_y_niveles():
    bz.inicializar()
    bid = bz.listar_buzones()[0]["id"]
    bz.guardar_correo(bid, 1, "<a@x>", datetime.now(), "notificacionesrut@dian.gov.co", "DIAN",
                      "Emplazamiento para declarar", "", [])
    bz.guardar_correo(bid, 2, "<b@x>", datetime.now(), "news@tienda.com", "", "Promo", "unsubscribe", [])
    bz.guardar_correo(bid, 2, "<b@x>", datetime.now(), "news@tienda.com", "", "Promo", "unsubscribe", [])  # duplicado
    nuevos = bz.bandeja()
    assert len(nuevos) == 1 and nuevos[0]["categoria"] == "DIAN"
    al = [a for a in bz.alertas(date.today()) if a["clave"].startswith("correo:")]
    assert al and al[0]["nivel"] == "CRITICO" and al[0]["accion"][0] == "atender"
    n = bz.niveles()
    n["DIAN"] = "NO"
    bz.guardar_niveles(n)
    assert not [a for a in bz.alertas(date.today()) if a["clave"].startswith("correo:")]
    bz.marcar(nuevos[0]["id"])
    assert not bz.bandeja()


def test_corrige_servidor_por_certificado(monkeypatch):
    import imaplib
    import ssl

    bz.inicializar()
    b = next(x for x in bz.listar_buzones() if x["email"] == "gerencia@viaindustrial.com")
    monkeypatch.setenv(bz.env_clave(b["email"]), "x")
    monkeypatch.setattr(bz, "nombres_certificado", lambda h, p=993: ["*.hosting.com", "srv7.hosting.com"])

    class Falso:
        def select(self, *a, **k):
            return "OK", [b"12"]

        def logout(self):
            pass

    def conectar(buz):
        if buz["imap_host"] == "mail.viaindustrial.com":
            raise ssl.SSLCertVerificationError("certificate verify failed: Hostname mismatch")
        return Falso()

    monkeypatch.setattr(bz, "_conectar", conectar)
    r = bz.probar(b["id"])
    assert r["ok"] and r["servidor"] == "srv7.hosting.com" and r["mensajes"] == 12
    hosts = {x["email"]: x["imap_host"] for x in bz.listar_buzones()}
    assert hosts["gerenciafenix@viaindustrial.com"] == "srv7.hosting.com"      # mismo dominio, mismo servidor
    assert hosts["equiposindustrialesfenix@gmail.com"] == "imap.gmail.com"
    _ = imaplib


def test_no_se_alerta_a_si_mismo_ni_por_pie_de_pagina():
    from modulos import buzones as b
    assert b.clasificar("gerenciafenix@viaindustrial.com", "⚠ 2 alertas críticas nuevas en Shaki", "", [])[0] == "OTRO"
    assert b.clasificar("x@y.com", "⚠ Alerta crítica: Juzgados y procesos", "juzgado", [])[0] == "OTRO"
    pie = "Bancolombia S.A. Vigilado Superintendencia Financiera de Colombia"
    assert b.clasificar("informacion@solicitudesgrupobancolombia.com.co", "Actualizamos el reglamento", pie, [])[0] != "JUDICIAL"
    assert b.clasificar("nuntius@fiscalia.gov.co", "NUC 110016000049202527335", "Fiscalía General", [])[0] == "JUDICIAL"
    cat, mot = b.clasificar("rappi@hello.rappi.com.co", "Notificación Juzgado 41 Civil", "", [])
    assert cat == "JUDICIAL" and "suplantación" in mot
