"""
Capa de integración de librerías del AGENTE ADMIN SHAKI.
Cada módulo del agente usa estas utilidades en lugar de importar directo.
"""
# Carga perezosa (PEP 562): cada utilidad se importa la primera vez que se pide. Antes «import core»
# arrastraba LangChain, SQLAlchemy, Jinja, etc. y alargaba varios segundos el arranque de Shaki.
_ORIGEN = {
    "es_dia_habil": "core.calendario_col", "es_festivo_colombia": "core.calendario_col",
    "get_engine": "core.db_sqlalchemy", "sql_query_df": ("core.db_sqlalchemy", "query_df"),
    "generar_pdf_tabla": "core.documentos_engine", "render_plantilla": "core.documentos_engine",
    "numero_a_letras": "core.formato_col", "valor_pesos": "core.formato_col",
    "fetch_url": "core.http_cliente",
    "chat_completar": "core.ia_engine", "ia_disponible": "core.ia_engine",
    "LIBRERIAS_POR_MODULO": "core.registro_libs", "librerias_disponibles": "core.registro_libs",
    "registrar_uso_libreria": "core.registro_libs", "verificar_librerias": "core.registro_libs",
}


def __getattr__(nombre: str):
    if nombre not in _ORIGEN:
        raise AttributeError(f"module 'core' has no attribute {nombre!r}")
    import importlib

    origen = _ORIGEN[nombre]
    modulo, attr = origen if isinstance(origen, tuple) else (origen, nombre)
    valor = getattr(importlib.import_module(modulo), attr)
    globals()[nombre] = valor
    return valor


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
