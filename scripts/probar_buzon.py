"""Registra (si hace falta) y prueba un buzón. Uso: python scripts/probar_buzon.py correo@dominio.com"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(override=True)
from modulos import buzones as b  # noqa: E402

correo = sys.argv[1].strip().lower()
b.inicializar()
b.agregar_buzon(correo)
bz = next(x for x in b.listar_buzones() if x["email"] == correo)
r = b.probar(bz["id"])
if r["ok"]:
    print(f"CONECTADO: {r.get('mensajes')} correos en la bandeja de {correo}"
          + (f" (servidor {r['servidor']})" if r.get("servidor") else ""))
else:
    print(f"ERROR: {r['error']}")
    sys.exit(1)
