"""Pruebas del radar tributario (DIAN + SHD Bogotá, NIT 901.146.454-6)."""
import os
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TMP = tempfile.mkdtemp()
os.environ["DATABASE_PATH"] = os.path.join(_TMP, "rt.db")

from config import cfg  # noqa: E402

cfg.DATABASE_PATH = os.environ["DATABASE_PATH"]
cfg.NIT_EMPRESA = "901146454-6"
cfg.APP_PUBLIC_URL = "https://shaki.example.com"
cfg.PAGOS_LINK_SECRET = "secreto"
cfg.IMPUESTOS_ALERTA_EMAILS = "directorfenix@viaindustrial.com,gerenciafenix@viaindustrial.com"

from database import get_conn, inicializar_db  # noqa: E402
from modulos import calendario_tributario_2026 as cal  # noqa: E402
from modulos import radar_tributario as rt  # noqa: E402


def _fecha(clave):
    return {o["clave"]: o["fecha"] for o in cal.obligaciones()}[clave]


class TestCalendarioOficial(unittest.TestCase):
    def test_retencion_digito_4(self):
        self.assertEqual(_fecha("DIAN-RET-2026-09"), "2026-10-15")
        self.assertEqual(_fecha("DIAN-RET-2026-06"), "2026-07-15")  # ajuste Ley 2578/2026 (antes 14-jul)
        self.assertEqual(_fecha("DIAN-RET-2026-12"), "2027-01-18")

    def test_iva_renta_exogena(self):
        self.assertEqual(_fecha("DIAN-IVAB-2026-5"), "2026-11-17")
        self.assertEqual(_fecha("DIAN-RENTA-2025-2"), "2026-07-15")
        self.assertEqual(_fecha("DIAN-EXO-2025"), "2026-05-29")

    def test_shd_bogota(self):
        self.assertEqual(_fecha("SHD-ICAB-2026-5"), "2026-12-11")
        self.assertEqual(_fecha("SHD-ICAB-2026-6"), "2027-02-12")
        self.assertEqual(_fecha("SHD-PRED-2026"), "2026-07-10")
        self.assertEqual(_fecha("SHD-VEH-2026"), "2026-07-24")

    def test_claves_unicas(self):
        claves = [o["clave"] for o in cal.obligaciones()]
        self.assertEqual(len(claves), len(set(claves)))


class TestRadar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inicializar_db()
        with mock.patch("modulos.radar_tributario.date") as d:
            d.today.return_value = date(2026, 10, 10)
            d.fromisoformat = date.fromisoformat
            rt.inicializar_tablas()
            rt.sincronizar()

    def test_nit_y_perfil(self):
        self.assertTrue(rt.calendario_aplica())
        conn = get_conn()
        estados = dict(conn.execute("SELECT clave, estado FROM impuestos_obligaciones").fetchall())
        conn.close()
        self.assertEqual(estados["DIAN-IVAC-2026-1"], "NO APLICA")  # cuatrimestral no aplica (es bimestral)
        self.assertEqual(estados["SHD-RETEICA-2026-5"], "NO APLICA")  # no es agente de ReteICA
        self.assertEqual(estados["DIAN-RET-2026-09"], "PENDIENTE")
        self.assertEqual(estados["DIAN-RET-2026-08"], "PRESENTADO")  # cierre inicial (vencida antes del 10-oct)

    def test_alerta_24h_solo_a_direccion_y_gerencia(self):
        obls = rt.para_alerta(date(2026, 10, 14))
        self.assertEqual([o["clave"] for o in obls], ["DIAN-RET-2026-09"])
        with mock.patch("conexiones.notificador.enviar_email", return_value=None):
            self.assertTrue(rt.enviar_alertas_24h(date(2026, 10, 14))["sin_canal"])
        self.assertEqual(len(rt.para_alerta(date(2026, 10, 14))), 1)  # no se marcó
        with mock.patch("conexiones.notificador.enviar_email", return_value=True) as em:
            r = rt.enviar_alertas_24h(date(2026, 10, 14))
            self.assertEqual((r["obligaciones"], r["correos"]), (1, 2))
            self.assertEqual(sorted(c.args[0] for c in em.call_args_list),
                             ["directorfenix@viaindustrial.com", "gerenciafenix@viaindustrial.com"])
            self.assertIn("PENDIENTE DE PRESENTACIÓN", em.call_args.args[2])
            self.assertIn("?presentar=", em.call_args.args[2])
            self.assertEqual(rt.enviar_alertas_24h(date(2026, 10, 14))["obligaciones"], 0)

    def test_boton_ya_lo_presente(self):
        o = [x for x in rt.listar() if x["clave"] == "SHD-ICAB-2026-5"][0]
        tok = rt.generar_token(o["id"])
        self.assertEqual(rt.verificar_token(tok), o["id"])
        self.assertIsNone(rt.verificar_token(tok[:-1] + ("0" if tok[-1] != "0" else "1")))
        self.assertTrue(rt.marcar_presentado(o["id"], por="enlace", referencia="F-123")["ok"])
        self.assertEqual(rt.obtener(o["id"])["estado"], "PRESENTADO")
        rt.sincronizar()  # re-sincronizar no deshace lo presentado
        self.assertEqual(rt.obtener(o["id"])["estado"], "PRESENTADO")


if __name__ == "__main__":
    unittest.main()
