"""Tests helpers RRHH (sin IA)."""
import os
import sys
import unittest
from datetime import date
from unittest import skipUnless

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.utils.rrhh_helpers import (
    calcular_vacaciones,
    dias_en_proceso,
    dias_habiles,
    proxima_dotacion,
)

try:
    import reportlab  # noqa: F401

    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class TestRRHHHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from database import inicializar_db

        inicializar_db()

    def test_dias_habiles_semana_laboral(self) -> None:
        self.assertEqual(dias_habiles(date(2026, 6, 1), date(2026, 6, 5)), 5)

    def test_dias_habiles_excluye_fin_de_semana(self) -> None:
        self.assertEqual(dias_habiles(date(2026, 6, 5), date(2026, 6, 8)), 2)

    def test_dias_habiles_fin_antes_inicio(self) -> None:
        self.assertEqual(dias_habiles(date(2026, 6, 10), date(2026, 6, 1)), 0)

    def test_proxima_dotacion_mas_4_meses(self) -> None:
        self.assertEqual(proxima_dotacion(date(2026, 1, 15)), date(2026, 5, 15))

    def test_calcular_vacaciones_estructura(self) -> None:
        r = calcular_vacaciones("Test Empleado", date(2020, 1, 1))
        self.assertIn("dias_causados", r)
        self.assertIn("dias_disponibles", r)
        self.assertGreaterEqual(r["dias_causados"], 0)

    def test_dias_en_proceso(self) -> None:
        self.assertGreaterEqual(dias_en_proceso(date.today()), 0)


@skipUnless(HAS_REPORTLAB, "reportlab no instalado")
class TestPDFCertificacion(unittest.TestCase):
    def test_generar_certificacion_crea_archivo(self) -> None:
        from dashboard.utils.pdf_generator import generar_certificacion

        path = generar_certificacion(
            "Juan Perez",
            "Analista",
            date(2022, 3, 1),
            2500000,
            "Indefinido",
            "1234567890",
        )
        self.assertTrue(os.path.isfile(path))
        if os.path.isfile(path):
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
