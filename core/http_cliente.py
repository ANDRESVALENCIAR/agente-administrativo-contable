"""Cliente HTTP con httpx + reintentos tenacity."""
import logging

logger = logging.getLogger(__name__)

try:
    import httpx

    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

try:
    from tenacity import retry, stop_after_attempt, wait_exponential

    _HAS_TENACITY = True
except ImportError:
    _HAS_TENACITY = False

import requests


def _fetch_requests(url: str, timeout: float, headers: dict) -> str:
    from core.registro_libs import registrar_uso_libreria

    registrar_uso_libreria("impuestos", "requests")
    resp = requests.get(url, timeout=timeout, headers=headers)
    resp.raise_for_status()
    return resp.text


def _fetch_httpx(url: str, timeout: float, headers: dict) -> str:
    from core.registro_libs import registrar_uso_libreria

    registrar_uso_libreria("impuestos", "httpx")
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


def fetch_url(url: str, timeout: float = 20.0, headers: dict | None = None) -> str:
    """
    GET con httpx (preferido) o requests.
    Reintentos automáticos si tenacity está instalado.
    """
    hdrs = headers or {"User-Agent": "AgenteAdminShaki/2.0"}

    if _HAS_HTTPX and _HAS_TENACITY:

        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
        def _get() -> str:
            return _fetch_httpx(url, timeout, hdrs)

        return _get()

    if _HAS_HTTPX:
        return _fetch_httpx(url, timeout, hdrs)

    if _HAS_TENACITY:

        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
        def _get() -> str:
            return _fetch_requests(url, timeout, hdrs)

        return _get()

    return _fetch_requests(url, timeout, hdrs)
