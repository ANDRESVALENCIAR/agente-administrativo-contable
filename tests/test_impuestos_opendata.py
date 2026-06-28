"""Tests calendario open data impuestos."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conexiones.opendata_impuestos import obtener_vencimientos_dian, obtener_vencimientos_shd_bogota
from modulos.impuestos_calendario import inicializar_tablas_calendario, sincronizar_calendario_opendata


class TestImpuestosOpenData(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["DATABASE_PATH"] = ":memory:"
        from database import inicializar_db

        inicializar_db()
        inicializar_tablas_calendario()

    def test_dian_opendata(self) -> None:
        items = obtener_vencimientos_dian(2026)
        self.assertGreater(len(items), 10)
        self.assertEqual(items[0]["entidad"], "DIAN")

    def test_shd_bogota(self) -> None:
        items = obtener_vencimientos_shd_bogota(2026)
        self.assertGreaterEqual(len(items), 5)
        self.assertTrue(any("ICA" in i["impuesto"] for i in items))

    def test_sincronizar_sqlite(self) -> None:
        n = sincronizar_calendario_opendata(2026)
        self.assertGreater(n, 15)


if __name__ == "__main__":
    unittest.main()
