"""Tests del chat interactivo por módulo."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import inicializar_db
from modulos.chat_interactivo import detectar_intencion, ejecutar_accion


class TestChatInteractivo(unittest.TestCase):
    """Detección de intenciones y acciones básicas."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DATABASE_PATH"] = ":memory:"
        inicializar_db()

    def test_detectar_aprobar_pago(self) -> None:
        self.assertEqual(detectar_intencion("aprobar pago 1"), "aprobar_pago")

    def test_detectar_ayuda(self) -> None:
        self.assertEqual(detectar_intencion("¿Qué puedes hacer?"), "ayuda")

    def test_detectar_correos(self) -> None:
        self.assertEqual(detectar_intencion("procesar correos ahora"), "procesar_correos")

    def test_ejecutar_ayuda(self) -> None:
        r = ejecutar_accion("ayuda", "ayuda")
        self.assertTrue(r["ejecutada"])
        self.assertIn("Pagos", r["resultado"])


if __name__ == "__main__":
    unittest.main()
