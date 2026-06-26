# Cómo ejecutar el Agente Administrativo-Contable

Proyecto en modo **demo** por defecto (sin credenciales reales). Solo necesitas Python 3.11+.

---

## 0. Preparación (una sola vez)

Abre PowerShell **en esta carpeta**:

```powershell
cd "C:\Users\micro\OneDrive - viaindustrial.com\0. TRABAJANDO HOY\agente-administrativo-contable"
```

### Entorno virtual

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Variables de entorno

```powershell
copy .env.example .env
```

No pegues credenciales reales para probar. Con los valores de `.env.example` el sistema usa **modo demo** (datos de ejemplo, sin llamadas a APIs externas).

Cuando quieras producción, edita `.env` con tus claves reales.

---

## 1. Agente autónomo (backend 24/7)

Ejecuta el orquestador con scheduler (correos, impuestos, CXP, etc.):

```powershell
cd "C:\Users\micro\OneDrive - viaindustrial.com\0. TRABAJANDO HOY\agente-administrativo-contable"
.\.venv\Scripts\Activate.ps1
python agente.py
```

- Crea/usa `agente.db` (SQLite local)
- Escribe logs en `agente.log`
- Ctrl+C para detener

---

## 2. Dashboard web

**Forma más fácil (Windows):** clic derecho en PowerShell dentro de la carpeta del proyecto:

```powershell
.\iniciar_dashboard.ps1
```

Abre el navegador solo y levanta el servidor en **http://localhost:8501**

**Forma manual:**

```powershell
cd "C:\Users\micro\OneDrive - viaindustrial.com\0. TRABAJANDO HOY\agente-administrativo-contable"
.\.venv\Scripts\Activate.ps1
python -m streamlit run dashboard/app.py
```

Luego abre manualmente: **http://localhost:8501**

> Si dice que `streamlit` no se reconoce, usa siempre `python -m streamlit run ...` con el Python del `.venv`.

Incluye panel de métricas, alertas, pagos, correos y documentos.

---

## 3. Chat conversacional

El chat **no es un servicio aparte**. Va integrado en el dashboard (columna derecha).

1. Arranca el dashboard (paso 2)
2. Usa el panel **Chat con el agente** o los botones de preguntas frecuentes
3. El historial se guarda en SQLite (`historial_chat`)

Sin `ANTHROPIC_API_KEY` real, las respuestas son simuladas (modo demo).

---

## 4. Pruebas

```powershell
cd "C:\Users\micro\OneDrive - viaindustrial.com\0. TRABAJANDO HOY\agente-administrativo-contable"
.\.venv\Scripts\Activate.ps1
python -m unittest discover tests -v
```

---

## Estructura del proyecto

```
agente-administrativo-contable/
├── agente.py              ← Agente autónomo (backend)
├── config.py
├── database.py
├── .env.example           ← Plantilla de variables (sin secretos reales)
├── requirements.txt
├── conexiones/            ← Gmail, Outlook, OneDrive, Claude
├── modulos/               ← 11 módulos funcionales
├── dashboard/
│   ├── app.py             ← Dashboard + chat
│   └── chat.py
├── documentos/            ← PDF, Word, plantillas
└── tests/
```

---

## Notas

- **No commitear** `.env`, `*.json` de OAuth, ni `agente.db`
- Para Railway: ver `railway.json` y `Procfile`
- Documentación extendida: `README.md`
