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
- **SQLite write pattern (avoid `database is locked`).** `database.py` helpers such as
  `crear_alerta` / `registrar_accion` open their *own* short-lived connection. Do not call them
  while another `sqlite3` connection in the same function is still holding an uncommitted write
  (README troubleshooting #7) — commit and `close()` first, then call the helper. Existing modules
  follow this (collect data during the write loop, close the connection, then create alerts).
- The worker (`python agente.py`) starts cleanly in demo mode: DB init, demo-data load, library
  registration, initial impuestos/CXP review, then `Calendario maestro activo`. The dashboard is
  the most convenient way to demonstrate end-to-end behavior.
