"""Vigilancia en tiempo real de PERSONAL ACTIVO/ (watchdog)."""
import logging
import threading
import time

logger = logging.getLogger(__name__)

_observer = None
_started = False
_lock = threading.Lock()
_debounce_timer: threading.Timer | None = None


def _programar_escaneo(segundos: float = 1.5) -> None:
    global _debounce_timer

    def _run() -> None:
        try:
            from modulos.carpetas_rrhh import escanear_carpetas_personal, generar_alertas_carpetas

            escanear_carpetas_personal()
            generar_alertas_carpetas()
        except Exception as e:
            logger.error("Error escaneo automático: %s", e)

    with _lock:
        if _debounce_timer is not None:
            _debounce_timer.cancel()
        _debounce_timer = threading.Timer(segundos, _run)
        _debounce_timer.daemon = True
        _debounce_timer.start()


def iniciar_watcher() -> bool:
    """Inicia Observer sobre PERSONAL ACTIVO/."""
    global _observer, _started

    with _lock:
        if _started:
            return _observer is not None

        from modulos.carpetas_rrhh import (
            escanear_carpetas_personal,
            marcar_watcher_activo,
            procesar_archivo_eliminado,
            procesar_archivo_nuevo,
            registrar_nuevo_empleado,
            retirar_empleado,
            ruta_personal_activo,
        )

        base = ruta_personal_activo()
        base.mkdir(parents=True, exist_ok=True)

        try:
            escanear_carpetas_personal()
        except Exception as e:
            logger.warning("Sync inicial carpetas: %s", e)

        try:
            from pathlib import Path

            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            class PersonalWatcher(FileSystemEventHandler):
                def on_created(self, event) -> None:
                    if event.is_directory:
                        nombre = Path(event.src_path).name
                        if not nombre.startswith("."):
                            registrar_nuevo_empleado(nombre)
                    else:
                        time.sleep(0.3)
                        procesar_archivo_nuevo(Path(event.src_path))
                    _programar_escaneo()

                def on_deleted(self, event) -> None:
                    if event.is_directory:
                        nombre = Path(event.src_path).name
                        if not nombre.startswith("."):
                            retirar_empleado(nombre)
                    else:
                        procesar_archivo_eliminado(Path(event.src_path))
                    _programar_escaneo()

                def on_modified(self, event) -> None:
                    if not event.is_directory:
                        procesar_archivo_nuevo(Path(event.src_path))
                        _programar_escaneo()

                def on_moved(self, event) -> None:
                    if event.src_path:
                        procesar_archivo_eliminado(Path(event.src_path))
                    if event.dest_path:
                        dest = Path(event.dest_path)
                        if dest.is_dir():
                            registrar_nuevo_empleado(dest.name)
                        else:
                            procesar_archivo_nuevo(dest)
                    _programar_escaneo()

            _observer = Observer()
            _observer.schedule(PersonalWatcher(), str(base.resolve()), recursive=True)
            _observer.daemon = True
            _observer.start()
            _started = True
            marcar_watcher_activo(True)
            logger.info("Watcher PERSONAL ACTIVO activo: %s", base.resolve())
            return True
        except ImportError:
            logger.warning("watchdog no instalado — escaneo solo manual")
            _started = True
            marcar_watcher_activo(False)
            return False
        except Exception as e:
            logger.error("Watcher no iniciado: %s", e)
            _started = True
            marcar_watcher_activo(False)
            return False


def iniciar_watcher_expediente() -> bool:
    return iniciar_watcher()
