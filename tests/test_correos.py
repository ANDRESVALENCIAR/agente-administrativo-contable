"""Tests del módulo de correos."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import inicializar_db
from modulos.correos import PROMPT_CLASIFICACION, normalizar_categoria


class TestCorreos(unittest.TestCase):
    """Pruebas unitarias de clasificación de correos."""

    def setUp(self) -> None:
        os.environ["DATABASE_PATH"] = ":memory:"
        inicializar_db()

    def test_prompt_clasificacion_formato(self) -> None:
        """El prompt de clasificación acepta variables."""
        prompt = PROMPT_CLASIFICACION.format(
            asunto="Factura 123",
            remitente="proveedor@test.com",
            cuerpo="Adjunto factura del mes",
        )
        self.assertIn("Factura 123", prompt)
        self.assertIn("factura", prompt.lower())

    def test_normalizar_categoria_v2(self) -> None:
        """Alias y categorías del prompt maestro v2."""
        self.assertEqual(normalizar_categoria("pago"), "solicitud_pago")
        self.assertEqual(normalizar_categoria("extracto_bancario"), "extracto_bancario")
        self.assertEqual(normalizar_categoria("cobranza"), "cobranza")
        self.assertEqual(normalizar_categoria("desconocido"), "otro")


if __name__ == "__main__":
    unittest.main()
