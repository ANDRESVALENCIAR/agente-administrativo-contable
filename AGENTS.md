# AGENTS.md

## Cursor Cloud specific instructions

Python project (Python 3.12 in this environment; README targets 3.11+). Two apps share the same
code + local SQLite `agente.db`:

- **Dashboard (primary, user-facing):** Streamlit web UI + integrated chat. Run with
  `.venv/bin/python -m streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0`
  then open `http://localhost:8501`. See `EJECUTAR.md` / `README.md` for details.
- **Agent worker (background):** `.venv/bin/python agente.py` — scheduler/orchestrator, logs to
  `agente.log`.

Dependencies live in a virtualenv at `.venv` (the update script creates it and installs
`requirements.txt`). Always invoke tools via `.venv/bin/python` (e.g. `.venv/bin/python -m ...`).

- **Tests:** `.venv/bin/python -m unittest discover tests` (27 tests, all pass).
- **Lint:** no linter is configured in this repo; use `.venv/bin/python -m compileall <dirs>` as a
  syntax check if needed.

Non-obvious caveats:

- **Demo mode is the default.** `.env` is created from `.env.example`; with placeholder
  `ANTHROPIC_API_KEY` the code runs in "modo demo" (sample data, no external API/Gmail/Graph
  calls). Real credentials in `.env` switch it to production. The dashboard sidebar shows
  `Activo · Demo`.
- **`python agente.py` hits a pre-existing SQLite self-deadlock in demo mode.** In
  `modulos/impuestos.py` `revisar_vencimientos` holds an uncommitted write on one `sqlite3`
  connection while `crear_alerta`/`registrar_accion` write from a second connection in the same
  process, raising `sqlite3.OperationalError: database is locked` (~30s timeout each) and killing
  the worker before the scheduler starts. This is a code bug (see README troubleshooting #7), not
  an environment issue — the worker still performs full startup (DB init, demo-data load, library
  registration) before failing. Do not "fix" the environment for this; it reproduces anywhere.
- The dashboard is the reliable way to demonstrate end-to-end behavior in demo mode.
