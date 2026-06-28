"""Tests de integración UI / módulos."""
import os
import sqlite3
import unittest

from config import cfg, en_modo_demo
from database import cargar_datos_demo, inicializar_db
from modulos.correos import obtener_destinos_correo, sincronizar_reglas_desde_config


class TestIntegracionUI(unittest.TestCase):
    """Verifica tablas y sincronización correos."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._db_backup = cfg.DATABASE_PATH + ".bak_test"
        if os.path.exists(cfg.DATABASE_PATH):
            os.replace(cfg.DATABASE_PATH, cls._db_backup)
        inicializar_db()
        if en_modo_demo():
            cargar_datos_demo()

    @classmethod
    def tearDownClass(cls) -> None:
        if os.path.exists(cfg.DATABASE_PATH):
            os.remove(cfg.DATABASE_PATH)
        if os.path.exists(cls._db_backup):
            os.replace(cls._db_backup, cfg.DATABASE_PATH)

    def test_tablas_modulos_existen(self) -> None:
        conn = sqlite3.connect(cfg.DATABASE_PATH)
        tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for t in ("reglas_correo", "cartera_cxc", "impuestos_maestro", "presupuesto_rubros"):
            self.assertIn(t, tablas)

    def test_destinos_correo_desde_bd(self) -> None:
        sincronizar_reglas_desde_config()
        destinos = obtener_destinos_correo()
        self.assertIn("factura", destinos)
        self.assertTrue(destinos["factura"])


if __name__ == "__main__":
    unittest.main()
