"""
Módulo de personal: novedades, certificaciones, contratos y prestaciones.
"""
import logging
import os
from datetime import datetime, date

import pandas as pd

from config import cfg
from core.calendario_col import es_dia_habil
from core.formato_col import numero_a_letras, valor_pesos
from conexiones.claude_client import llamar_claude
from conexiones.gmail_client import enviar_correo
from conexiones.onedrive_client import leer_excel, escribir_excel
from database import crear_alerta, registrar_accion, registrar_documento
from documentos.generador_pdf import generar_pdf_texto
from documentos.generador_word import generar_word_desde_plantilla, generar_word_texto

logger = logging.getLogger(__name__)


def actualizar_novedades_diarias() -> None:
    """Procesa permisos, incapacidades, vacaciones y préstamos del día."""
    logger.info("Actualizando novedades de personal...")
    try:
        df = leer_excel(cfg.EXCEL_PERSONAL_ID or "demo", "NOVEDADES")
        if df.empty:
            df = pd.DataFrame(
                [{"EMPLEADO": "Demo", "TIPO": "Permiso", "FECHA": date.today().isoformat(), "ESTADO": "REGISTRADO"}]
            )
        df["FECHA_PROCESO"] = datetime.now().isoformat()
        escribir_excel(cfg.EXCEL_PERSONAL_ID or "demo", "NOVEDADES", df)
        registrar_accion("personal", "actualizar_novedades_diarias", f"{len(df)} novedades", "EXITOSO")
    except Exception as e:
        logger.error("Error actualizar_novedades_diarias: %s", e)
        registrar_accion("personal", "actualizar_novedades_diarias", str(e), "ERROR", detalle_error=str(e))


def elaborar_certificacion(empleado: str, tipo: str) -> str:
    """
    Genera certificación laboral en PDF.

    Args:
        empleado: Nombre del empleado.
        tipo: laboral, ingresos, tiempo_servicio o cargo.

    Returns:
        Ruta del PDF generado.
    """
    logger.info("Certificación %s para %s", tipo, empleado)
    try:
        prompt = f"""Genera certificación {tipo} para empleado {empleado} de {cfg.NOMBRE_EMPRESA}
(NIT {cfg.NIT_EMPRESA}, {cfg.CIUDAD_EMPRESA}). Formato legal colombiano, listo para firmar."""
        texto = llamar_claude(prompt, modulo="personal", max_tokens=1500)
        os.makedirs("documentos/generados", exist_ok=True)
        nombre = f"cert_{tipo}_{empleado.replace(' ', '_')}.pdf"
        path = os.path.join("documentos/generados", nombre)
        generar_pdf_texto(path, f"Certificación {tipo.title()}", texto)
        registrar_documento("PDF", nombre, path, "personal", f"Certificación {tipo} — {empleado}")
        registrar_accion("personal", "elaborar_certificacion", f"{empleado} — {tipo}", "EXITOSO")
        return path
    except Exception as e:
        logger.error("Error elaborar_certificacion: %s", e)
        return ""


def calcular_prima(empleado_id: str, periodo: str) -> dict:
    """
    Calcula prima de servicios según ley colombiana (medio salario por semestre).

    Args:
        empleado_id: Identificador del empleado.
        periodo: Periodo semestral (ej. 2026-1).

    Returns:
        Dict con salario base, días trabajados y prima calculada.
    """
    logger.info("Calculando prima %s — %s", empleado_id, periodo)
    df = leer_excel(cfg.EXCEL_PERSONAL_ID or "demo", "NOMINA")
    salario = 2500000.0
    if not df.empty and "SALARIO" in df.columns:
        fila = df[df.get("ID", df.columns[0]).astype(str) == str(empleado_id)]
        if not fila.empty:
            salario = float(fila.iloc[0].get("SALARIO", salario))
    prima = salario / 2
    return {
        "empleado_id": empleado_id,
        "periodo": periodo,
        "salario": salario,
        "prima": prima,
        "prima_formato": valor_pesos(prima),
        "prima_letras": numero_a_letras(prima),
        "dia_habil": es_dia_habil(),
    }


def calcular_vacaciones(empleado_id: str) -> dict:
    """
    Calcula vacaciones: 15 días hábiles por año según ley colombiana.

    Args:
        empleado_id: Identificador del empleado.

    Returns:
        Dict con días acumulados y pendientes.
    """
    logger.info("Calculando vacaciones %s", empleado_id)
    df = leer_excel(cfg.EXCEL_PERSONAL_ID or "demo", "PERSONAL")
    anos = 1
    if not df.empty:
        fila = df[df.get("ID", df.columns[0]).astype(str) == str(empleado_id)]
        if not fila.empty and "FECHA_INGRESO" in fila.columns:
            ingreso = pd.to_datetime(fila.iloc[0]["FECHA_INGRESO"])
            anos = max(1, (date.today() - ingreso.date()).days // 365)
    dias = anos * 15
    return {"empleado_id": empleado_id, "dias_acumulados": dias, "dias_habiles_por_ano": 15}


def revisar_contratos() -> None:
    """Alerta contratos que vencen en los próximos 30 días."""
    logger.info("Revisando vencimiento de contratos...")
    try:
        df = leer_excel(cfg.EXCEL_CONTRATOS_ID or cfg.EXCEL_PERSONAL_ID or "demo", "CONTRATOS")
        if df.empty:
            df = pd.DataFrame(
                [{"EMPLEADO": "Demo", "FECHA_FIN": "2026-07-15", "TIPO": "Término fijo"}]
            )
        hoy = date.today()
        for _, fila in df.iterrows():
            try:
                fin = pd.to_datetime(fila["FECHA_FIN"]).date()
            except Exception:
                continue
            dias = (fin - hoy).days
            if 0 <= dias <= 30:
                crear_alerta(
                    "URGENTE",
                    "personal",
                    f"Contrato vence: {fila.get('EMPLEADO', 'N/A')}",
                    f"Vence en {dias} días ({fin.strftime('%d/%m/%Y')})",
                )
        registrar_accion("personal", "revisar_contratos", "Revisión completada", "EXITOSO")
    except Exception as e:
        logger.error("Error revisar_contratos: %s", e)
        registrar_accion("personal", "revisar_contratos", str(e), "ERROR", detalle_error=str(e))


def elaborar_contrato(tipo: str, datos: dict) -> str:
    """
    Genera contrato laboral o de prestación de servicios en DOCX.

    Args:
        tipo: LABORAL_TERMINO_FIJO, LABORAL_INDEFINIDO o PRESTACION_SERVICIOS.
        datos: Datos del contratado (nombre, cédula, cargo, salario, etc.).

    Returns:
        Ruta del archivo DOCX generado.
    """
    logger.info("Elaborando contrato %s", tipo)
    plantillas = {
        "LABORAL_TERMINO_FIJO": "contrato_laboral.txt",
        "LABORAL_INDEFINIDO": "contrato_laboral.txt",
        "PRESTACION_SERVICIOS": "contrato_prestacion.txt",
    }
    plantilla = plantillas.get(tipo, "contrato_laboral.txt")
    prompt = f"""Completa este contrato tipo {tipo} con los datos:
{datos}
Empresa: {cfg.NOMBRE_EMPRESA}, NIT {cfg.NIT_EMPRESA}, {cfg.CIUDAD_EMPRESA}.
Normativa laboral colombiana vigente."""
    texto = llamar_claude(prompt, modulo="personal", max_tokens=3000)
    os.makedirs("documentos/generados", exist_ok=True)
    nombre = f"contrato_{tipo}_{datetime.now().strftime('%Y%m%d')}.docx"
    path = os.path.join("documentos/generados", nombre)
    try:
        generar_word_desde_plantilla(
            os.path.join("documentos/plantillas", plantilla),
            path,
            {**datos, "NOMBRE_EMPRESA": cfg.NOMBRE_EMPRESA, "NIT": cfg.NIT_EMPRESA, "TEXTO_CLAUDE": texto},
        )
    except Exception:
        generar_word_texto(path, f"Contrato {tipo}", texto)
    registrar_documento("DOCX", nombre, path, "personal", f"Contrato {tipo}")
    registrar_accion("personal", "elaborar_contrato", tipo, "EXITOSO")
    return path
