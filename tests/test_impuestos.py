"""Tests del módulo de impuestos."""
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modulos.impuestos import _calcular_dias_restantes, _nivel_alerta


class TestImpuestos(unittest.TestCase):
    """Pruebas de cálculo de vencimientos."""

    def test_nivel_critico(self) -> None:
        """1 día o menos es CRITICO."""
        self.assertEqual(_nivel_alerta(1), "CRITICO")
        self.assertEqual(_nivel_alerta(0), "CRITICO")

    def test_nivel_urgente(self) -> None:
        """5 días o menos es URGENTE."""
        self.assertEqual(_nivel_alerta(5), "URGENTE")

    def test_nivel_aviso(self) -> None:
        """15 días o menos es AVISO."""
        self.assertEqual(_nivel_alerta(15), "AVISO")

    def test_sin_alerta(self) -> None:
        """Más de 15 días no genera alerta."""
        self.assertIsNone(_nivel_alerta(20))

    def test_dias_restantes(self) -> None:
        """Calcula diferencia de días correctamente."""
        futuro = date.today() + timedelta(days=10)
        dias = _calcular_dias_restantes(futuro)
        self.assertEqual(dias, 10)


if __name__ == "__main__":
    unittest.main()
