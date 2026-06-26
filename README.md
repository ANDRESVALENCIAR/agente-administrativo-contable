# Agente Administrativo-Contable

Sistema autónomo de gestión administrativa y contable para empresas colombianas. Combina un **agente Python 24/7** con un **dashboard Streamlit** y **chat conversacional con Claude**.

## Arquitectura

| Componente | Descripción |
|------------|-------------|
| `agente.py` | Orquestador con scheduler (Railway worker) |
| `dashboard/app.py` | Interfaz web con métricas + chat |
| `conexiones/` | Gmail, Outlook, OneDrive, Claude API |
| `modulos/` | 11 módulos funcionales (correos, impuestos, pagos, etc.) |
| `agente.db` | SQLite local con logs, alertas y estadísticas |

**Stack:** Python 3.11+, Anthropic Claude, Google Gmail API, Microsoft Graph, Streamlit, Plotly.

## Requisitos

- Python 3.11 o superior
- Cuenta [Anthropic](https://console.anthropic.com) (API key)
- [Google Cloud](https://console.cloud.google.com) — Gmail API (opcional)
- [Azure Portal](https://portal.azure.com) — App Registration para M365 (opcional)
- [Railway](https://railway.app) para despliegue (opcional)

## Instalación

```powershell
cd agente-admin
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env` con sus credenciales reales.

## Credenciales

### ANTHROPIC_API_KEY
1. Ir a [console.anthropic.com](https://console.anthropic.com) → API Keys
2. Crear clave y pegarla en `.env`

### Gmail
1. Google Cloud Console → Crear proyecto → Habilitar **Gmail API**
2. Crear credenciales OAuth 2.0 (Desktop)
3. Descargar JSON como `conexiones/gmail_credentials.json`
4. Primera ejecución abrirá navegador para autorizar

### Microsoft 365 (Outlook + OneDrive)
1. Azure Portal → App registrations → New registration
2. Permisos de aplicación: `Mail.Read`, `Mail.Send`, `Files.ReadWrite.All`
3. Crear client secret
4. Copiar `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_TENANT_ID` en `.env`

### Excel en OneDrive
1. Subir archivos Excel a OneDrive
2. Obtener `file_id` de cada archivo (Graph Explorer o URL del archivo)
3. Configurar `EXCEL_*_ID` en `.env`

## Modo demo

Si `ANTHROPIC_API_KEY` no está configurada (o es placeholder), el sistema arranca en **modo demo** con datos de ejemplo. El dashboard y el agente funcionan sin APIs externas.

## Ejecución local

**Terminal 1 — Agente autónomo:**
```powershell
cd agente-admin
python agente.py
```

**Terminal 2 — Dashboard:**
```powershell
cd agente-admin
streamlit run dashboard/app.py
```

Abrir `http://localhost:8501`

## Despliegue en Railway

1. Subir repositorio a GitHub
2. Railway → New Project → Deploy from GitHub
3. Agregar todas las variables de `.env` en Railway Variables
4. Worker: `python agente.py` (ver `railway.json`)
5. Web (opcional): `streamlit run dashboard/app.py --server.port $PORT --server.address 0.0.0.0`

## Uso del dashboard

- **Inicio:** métricas, alertas activas, gráfico de correos
- **Alertas / Pagos:** resolver alertas, aprobar o rechazar pagos
- **Chat (columna derecha):** preguntas en lenguaje natural con contexto en tiempo real

## Columnas requeridas por Excel

| Archivo | Hoja | Columnas clave |
|---------|------|----------------|
| IMPUESTOS | IMPUESTOS | IMPUESTO, PERIODO, FECHA_VENCIMIENTO, ESTADO, FORMULARIO |
| CXP_CXC | CXP_ADMINISTRATIVOS | PROVEEDOR, CONCEPTO, MONTO, FECHA_VENCIMIENTO, ESTADO |
| CXP_CXC | CARTERA_CLIENTES | CLIENTE, NIT, DIAS_MORA, SALDO |
| PERSONAL | NOMINA | ID, SALARIO, deducciones |
| PERSONAL | NOVEDADES | EMPLEADO, TIPO, FECHA, ESTADO |
| VENTAS | VENTAS | ASESOR, VENTAS_NETAS, RECAUDO_PCT, ANTICIPO, EMAIL |
| PRESUPUESTO | PRESUPUESTO | RUBRO, PRESUPUESTO, EJECUTADO |

## Troubleshooting

1. **`ModuleNotFoundError`** — Activar venv e instalar `pip install -r requirements.txt`
2. **Modo demo siempre activo** — Revisar que `ANTHROPIC_API_KEY` no sea placeholder
3. **Gmail auth falla** — Verificar `gmail_credentials.json` y scopes
4. **Microsoft token error** — Revisar permisos de aplicación en Azure
5. **Excel vacío** — Verificar `EXCEL_*_ID` y permisos Files.ReadWrite
6. **Streamlit no carga** — Ejecutar desde carpeta `agente-admin`
7. **SQLite locked** — No compartir `agente.db` entre procesos sin WAL
8. **Rate limit Claude** — El cliente reintenta 3 veces automáticamente
9. **PDF con caracteres raros** — fpdf2 usa Helvetica (latin-1); evitar tildes en títulos muy largos
10. **Scheduler no corre** — Verificar zona horaria del servidor Railway (UTC)

## Extender el sistema

1. Crear `modulos/mi_modulo.py` con funciones y docstrings
2. Registrar tarea en `agente.py` con `schedule.every()...`
3. Agregar página en `dashboard/app.py` si necesita UI
4. Registrar acciones con `database.registrar_accion()`

## Tests

```powershell
python -m unittest discover tests
```

## Versiones de librerías

- `anthropic>=0.40.0` — requerido para modelos Claude 4.x y prompt caching
- `streamlit>=1.40.0` — `st.rerun()` y layout wide
- `fpdf2>=2.8.0` — API `FPDF` con `new_x`/`new_y` en celdas
