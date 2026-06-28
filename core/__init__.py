"""
Capa de integración de librerías del AGENTE ADMIN SHAKI.
Cada módulo del agente usa estas utilidades en lugar de importar directo.
"""
from core.calendario_col import es_dia_habil, es_festivo_colombia
from core.db_sqlalchemy import get_engine, query_df as sql_query_df
from core.documentos_engine import generar_pdf_tabla, render_plantilla
from core.formato_col import numero_a_letras, valor_pesos
from core.http_cliente import fetch_url
from core.ia_engine import chat_completar, ia_disponible
from core.registro_libs import (
    LIBRERIAS_POR_MODULO,
    librerias_disponibles,
    registrar_uso_libreria,
    verificar_librerias,
)

__all__ = [
    "LIBRERIAS_POR_MODULO",
    "chat_completar",
    "es_dia_habil",
    "es_festivo_colombia",
    "fetch_url",
    "generar_pdf_tabla",
    "get_engine",
    "ia_disponible",
    "librerias_disponibles",
    "numero_a_letras",
    "registrar_uso_libreria",
    "render_plantilla",
    "sql_query_df",
    "valor_pesos",
    "verificar_librerias",
]
