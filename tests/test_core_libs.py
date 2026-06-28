"""Tests del paquete core de librerías."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.formato_col import numero_a_letras, valor_pesos
from core.registro_libs import verificar_librerias


class TestCoreLibs(unittest.TestCase):
    def test_verificar_librerias(self) -> None:
        r = verificar_librerias()
        self.assertIn("activas", r)
        self.assertIn("detalle", r)

    def test_valor_pesos(self) -> None:
        txt = valor_pesos(1500000)
        self.assertIn("1", txt)

    def test_numero_a_letras(self) -> None:
        txt = numero_a_letras(100)
        self.assertTrue(len(txt) > 0)


if __name__ == "__main__":
    unittest.main()
