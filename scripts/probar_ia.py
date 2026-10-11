"""Prueba la clave de Anthropic guardada en .env con una pregunta mínima (la usa configurar_ia.ps1)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(override=True)


def main() -> int:
    clave = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not clave or clave.startswith("sk-ant-xxx"):
        print("No hay clave guardada en .env")
        return 1
    try:
        import anthropic
    except ImportError:
        print("Falta la librería anthropic: corra actualizar_shaki.ps1")
        return 1
    from config import cfg

    modelo = os.getenv("MODELO_COMPLEJO", cfg.MODELO_COMPLEJO)
    try:
        r = anthropic.Anthropic(api_key=clave).messages.create(
            model=modelo, max_tokens=200, messages=[{"role": "user", "content": "Responde solo: Shaki listo"}])
    except anthropic.AuthenticationError:
        print("La clave NO es válida (Anthropic la rechazó). Revise que la copió completa.")
        return 1
    except anthropic.PermissionDeniedError:
        print("La clave es válida pero la cuenta no tiene permiso para ese modelo o no tiene saldo.")
        return 1
    except anthropic.NotFoundError:
        print(f"El modelo {modelo} no está disponible para esta cuenta.")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo conectar con Anthropic: {e}")
        return 1
    texto = "".join(b.text for b in r.content if b.type == "text").strip()
    print(f"OK · modelo {modelo} · respuesta: {texto}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
