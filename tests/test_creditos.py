"""Tests del módulo de créditos."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modulos.creditos import _calcular_indicadores


class TestCreditos(unittest.TestCase):
    """Pruebas de indicadores financieros."""

    def test_indicadores_basicos(self) -> None:
        """Calcula indicadores con datos de ejemplo."""
        datos = {
            "ingresos_mensuales": 10000000,
            "deuda_actual": 2000000,
            "activos": 50000000,
            "cupo_solicitado": 5000000,
        }
        ind = _calcular_indicadores(datos)
        self.assertIn("capacidad_pago", ind)
        self.assertIn("endeudamiento", ind)
        self.assertIn("liquidez", ind)
        self.assertGreater(ind["liquidez"], 0)


if __name__ == "__main__":
    unittest.main()
