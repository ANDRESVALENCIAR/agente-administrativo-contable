"""
Cliente OneDrive/Excel via Microsoft Graph API.
Lee y escribe archivos Excel en OneDrive.
"""
import logging
from io import BytesIO
from typing import Any

import pandas as pd
import requests

from config import cfg, microsoft_configurado, en_modo_demo
from conexiones.outlook_client import get_headers

logger = logging.getLogger(__name__)
BASE_URL = "https://graph.microsoft.com/v1.0"


def _datos_demo_impuestos() -> pd.DataFrame:
    """DataFrame de ejemplo para impuestos en modo demo."""
    return pd.DataFrame(
        [
            {
                "IMPUESTO": "IVA",
                "PERIODO": "2026-02",
                "FECHA_VENCIMIENTO": "2026-03-18",
                "ESTADO": "PENDIENTE",
                "FECHA_PRESENTACION": "",
                "FORMULARIO": "350",
                "OBSERVACIONES": "",
            },
            {
                "IMPUESTO": "Retención en la fuente",
                "PERIODO": "2026-02",
                "FECHA_VENCIMIENTO": "2026-03-12",
                "ESTADO": "PENDIENTE",
                "FECHA_PRESENTACION": "",
                "FORMULARIO": "350",
                "OBSERVACIONES": "",
            },
        ]
    )


def _datos_demo_cxp() -> pd.DataFrame:
    """DataFrame de ejemplo para CXP administrativos."""
    return pd.DataFrame(
        [
            {
                "PROVEEDOR": "Servicios XYZ S.A.S.",
                "CONCEPTO": "Mantenimiento",
                "MONTO": 2500000,
                "FECHA_VENCIMIENTO": "2026-06-20",
                "ESTADO": "PENDIENTE",
                "PRIORIDAD": "",
                "CUENTA_BANCARIA": "Bancolombia ***1234",
                "TIPO_PAGO": "Transferencia",
            },
            {
                "PROVEEDOR": "Papelería Central",
                "CONCEPTO": "Suministros",
                "MONTO": 450000,
                "FECHA_VENCIMIENTO": "2026-06-26",
                "ESTADO": "PENDIENTE",
                "PRIORIDAD": "",
                "CUENTA_BANCARIA": "Davivienda ***5678",
                "TIPO_PAGO": "Transferencia",
            },
        ]
    )


def leer_excel(file_id: str, hoja: str, rango: str | None = None) -> pd.DataFrame:
    """
    Lee una hoja de un Excel en OneDrive y retorna un DataFrame.

    Args:
        file_id: ID del archivo en OneDrive.
        hoja: Nombre de la hoja.
        rango: Rango opcional (no usado en descarga completa).

    Returns:
        DataFrame con los datos de la hoja.
    """
    if en_modo_demo() or not microsoft_configurado():
        logger.info("Modo demo: retornando datos de ejemplo para hoja %s", hoja)
        if "IMPUEST" in hoja.upper() or file_id == cfg.EXCEL_IMPUESTOS_ID:
            return _datos_demo_impuestos()
        if "CXP" in hoja.upper() or file_id == cfg.EXCEL_CXP_CXC_ID:
            return _datos_demo_cxp()
        return pd.DataFrame()

    try:
        url = f"{BASE_URL}/me/drive/items/{file_id}/content"
        resp = requests.get(url, headers=get_headers(), timeout=60)
        resp.raise_for_status()
        df = pd.read_excel(BytesIO(resp.content), sheet_name=hoja)
        return df
    except Exception as e:
        logger.error("Error leyendo Excel %s hoja %s: %s", file_id, hoja, e)
        return pd.DataFrame()


def escribir_excel(
    file_id: str, hoja: str, datos_df: pd.DataFrame, fila_inicio: int = 2
) -> bool:
    """
    Escribe datos de un DataFrame en una hoja de Excel en OneDrive.

    Args:
        file_id: ID del archivo.
        hoja: Nombre de la hoja.
        datos_df: DataFrame a escribir.
        fila_inicio: Fila inicial (reservado para uso futuro).

    Returns:
        True si la escritura fue exitosa.
    """
    if en_modo_demo() or not microsoft_configurado():
        logger.info("[Demo] Escritura simulada en Excel %s hoja %s", file_id, hoja)
        return True
    try:
        session_url = f"{BASE_URL}/me/drive/items/{file_id}/workbook/createSession"
        session = requests.post(
            session_url, headers=get_headers(), json={"persistChanges": True}, timeout=30
        )
        session_id = session.json().get("id")
        headers_ws = {**get_headers(), "workbook-session-id": session_id}

        valores = [datos_df.columns.tolist()] + datos_df.values.tolist()
        col_fin = chr(ord("A") + len(datos_df.columns) - 1)
        rango_addr = f"A1:{col_fin}{len(valores)}"

        url = (
            f"{BASE_URL}/me/drive/items/{file_id}/workbook/worksheets/{hoja}"
            f"/range(address='{rango_addr}')"
        )
        resp = requests.patch(url, headers=headers_ws, json={"values": valores}, timeout=60)
        resp.raise_for_status()

        requests.post(
            f"{BASE_URL}/me/drive/items/{file_id}/workbook/closeSession",
            headers=headers_ws,
            timeout=30,
        )
        return True
    except Exception as e:
        logger.error("Error escribiendo Excel %s: %s", file_id, e)
        return False


def actualizar_celda(file_id: str, hoja: str, celda: str, valor: Any) -> bool:
    """Actualiza el valor de una celda específica. Ej: celda='B5'."""
    if en_modo_demo() or not microsoft_configurado():
        logger.info("[Demo] Celda %s=%s simulada", celda, valor)
        return True
    try:
        url = (
            f"{BASE_URL}/me/drive/items/{file_id}/workbook/worksheets/{hoja}"
            f"/range(address='{celda}')"
        )
        resp = requests.patch(url, headers=get_headers(), json={"values": [[valor]]}, timeout=30)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error("Error actualizando celda %s en %s: %s", celda, file_id, e)
        return False


def buscar_en_excel(file_id: str, hoja: str, columna: str, valor: str) -> dict[str, Any] | None:
    """Busca una fila donde columna == valor. Retorna la fila como dict."""
    df = leer_excel(file_id, hoja)
    if df.empty or columna not in df.columns:
        return None
    resultado = df[df[columna].astype(str) == str(valor)]
    if resultado.empty:
        return None
    return resultado.iloc[0].to_dict()
