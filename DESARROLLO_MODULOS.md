# Guía de desarrollo — todos los módulos EIF SAS

**Empresa:** EIF SAS · NIT 901146454-6 · Bogotá D.C.  
**Agente:** AGENTE ADMIN SHAKI

## Arranque rápido

```bash
# Instalación (una vez)
pip install -r requirements.txt
cp .env.example .env

# Opción A — todo junto (tmux)
./iniciar_todo.sh

# Opción B — terminales separadas
./iniciar_dashboard.sh    # http://localhost:8501
./iniciar_agente.sh       # backend 24/7
```

## Mapa de módulos

| Módulo | UI (`dashboard/paginas/`) | Backend (`modulos/`) | Tablas SQLite |
|--------|---------------------------|----------------------|---------------|
| Inicio | `inicio.py` | `database.py` stats | alertas, log_acciones |
| Calendario | `calendario.py` | `utils/calendario_maestro.py` | calendario_maestro |
| Alertas | `alertas.py` | `alertas_globales.py` | alertas |
| Contabilidad | `contabilidad.py` | `contable.py` | conciliacion_bancaria |
| Impuestos | `impuestos.py` | `impuestos.py`, `impuestos_calendario.py` | impuestos_maestro, calendario_tributario |
| CXP/CXC | `cxp_cxc.py` | `cxp_cxc.py` | cartera_cxc, cxp_programados |
| Pagos | `pagos.py` | `pagos.py` | pagos_pendientes, historial_pagos |
| Correos | `correos.py` | `correos.py` | correos_procesados, reglas_correo |
| Créditos | `creditos.py` | `creditos.py` | creditos_analizados |
| Comisiones | `comisiones.py` | `comisiones.py` | comisiones_detalle |
| Personal | `personal.py`, `personal_expedientes.py` | `personal.py`, `carpetas_rrhh.py` | novedades_rrhh, empleados_carpetas |
| Presupuesto | `presupuesto.py` | `presupuesto.py` | presupuesto_rubros |
| Jurídico | `juridico.py` | `juridico.py` | normatividad, politicas_internas |
| Documentos | `documentos.py` | generadores en `documentos/` | documentos_generados |
| Estadísticas | `estadisticas.py` | `log_acciones`, `uso_tokens_diario` | — |
| Chat | columna en `app.py` | `chat_interactivo.py`, `chat.py` | historial_chat |

## Callbacks del calendario (agente automático)

Definidos en `modulos/calendario_callbacks.py` y sembrados en `utils/calendario_maestro.py`:

- RRHH: escaneo carpetas, alertas expedientes, novedades, contratos
- Impuestos: vencimientos, recordatorios 48h/24h, open data DIAN/SHD
- Pagos: CXP diario, revisión nómina
- Correos: procesar cada 30 min, resumen 18:00
- CXP/CXC: reunión semanal, sync cartera
- Créditos: mora clientes
- Contabilidad: conciliación bancaria
- Comisiones: liquidación mensual (día 5)
- Presupuesto: análisis mensual (día 5)
- Jurídico: normatividad semanal

## Cómo extender un módulo

1. **Lógica:** crear/editar `modulos/mi_modulo.py`
2. **UI:** crear `dashboard/paginas/mi_modulo.py` con `render()`
3. **Menú:** registrar en `dashboard/app.py` → `PAGINAS`
4. **BD:** tabla en `database_modulos.py` o `modulos/rrhh_db.py`
5. **Scheduler:** callback en `calendario_callbacks.py` + plantilla en `sembrar_tareas_iniciales()`
6. **Chat:** intención en `modulos/chat_interactivo.py`
7. **Tests:** `tests/test_mi_modulo.py`

## Pendientes sugeridos (producción EIF SAS)

| Prioridad | Tarea |
|-----------|-------|
| Alta | Credenciales reales en `.env` (Anthropic, Gmail, M365, Twilio) |
| Alta | `RRHH_CARPETA_PERSONAL` → ruta OneDrive real |
| Alta | IDs Excel OneDrive (`EXCEL_*_ID`) |
| Media | DIAN SOAP / facturación electrónica (`zeep`) |
| Media | Despliegue Railway (worker + web) |
| Baja | Unificar tablas legacy RRHH (`*_rrhh` → tablas activas) |

## Comandos útiles

```bash
python -m unittest discover tests -v   # pruebas
python agente.py                       # solo backend
streamlit run dashboard/app.py         # solo front
```

## Modo demo vs producción

- **Demo:** sin `ANTHROPIC_API_KEY` real → datos de ejemplo, sin APIs externas
- **Producción:** completar `.env` y archivos OAuth (`gmail_credentials.json`, Azure M365)
