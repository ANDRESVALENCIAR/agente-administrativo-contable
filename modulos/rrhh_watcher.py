"""Vigilancia de carpeta PERSONAL ACTIVO — sync automática al agregar archivos."""
import logging
import threading

logger = logging.getLogger(__name__)

_observer = None
_started = False
_start_lock = threading.Lock()


def iniciar_watcher_expediente() -> bool:
    """
    Inicia watchdog sobre RRHH_CARPETA_PERSONAL (una sola vez por proceso).

    Returns:
        True si el watcher quedó activo.
    """
    global _observer, _started

    with _start_lock:
        if _started:
            return _observer is not None

        from modulos.rrhh_expediente import carpeta_personal_base, programar_sync_debounce, sincronizar_expediente

        base = carpeta_personal_base()
        base.mkdir(parents=True, exist_ok=True)

        try:
            sincronizar_expediente()
        except Exception as e:
            logger.warning("Sync inicial expediente: %s", e)

        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            class _Handler(FileSystemEventHandler):
                def on_any_event(self, event) -> None:
                    if event.is_directory:
                        return
                    src = getattr(event, "dest_path", None) or event.src_path
                    if src and ("desktop.ini" in src.lower() or src.endswith("~")):
                        return
                    programar_sync_debounce(1.5)

            _observer = Observer()
            _observer.schedule(_Handler(), str(base.resolve()), recursive=True)
            _observer.daemon = True
            _observer.start()
            _started = True
            logger.info("Watcher expediente RRHH activo en: %s", base.resolve())
            return True
        except ImportError:
            logger.warning("watchdog no instalado — sync solo manual")
            _started = True
            return False
        except Exception as e:
            logger.error("No se pudo iniciar watcher: %s", e)
            _started = True
            return False


def detener_watcher() -> None:
    global _observer, _started
    if _observer is not None:
        _observer.stop()
        _observer.join(timeout=3)
        _observer = None
    _started = False
