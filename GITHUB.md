# Subir el proyecto a GitHub

## Requisitos

- [Git](https://git-scm.com/download/win) instalado
- Cuenta en [GitHub](https://github.com)
- (Opcional) [GitHub CLI](https://cli.github.com/) → comando `gh`

**Nunca subas:** `.env`, credenciales `*.json`, `agente.db`, `.venv/` (ya están en `.gitignore`).

---

## Opción A — Con GitHub CLI (más rápido)

En PowerShell, dentro de esta carpeta:

```powershell
cd "C:\Users\micro\OneDrive - viaindustrial.com\0. TRABAJANDO HOY\agente-administrativo-contable"

git init
git add .
git status
git commit -m "Initial commit: agente administrativo-contable con dashboard y chat"

gh auth login
gh repo create agente-administrativo-contable --private --source=. --remote=origin --push
```

Cambia `--private` por `--public` si quieres repo público.

---

## Opción B — Manual (sin `gh`)

### 1. Crear repo vacío en GitHub

1. Entra a https://github.com/new
2. Nombre: `agente-administrativo-contable`
3. **No** marques "Add README" (ya tienes archivos locales)
4. Crear repositorio

### 2. Subir código desde tu PC

```powershell
cd "C:\Users\micro\OneDrive - viaindustrial.com\0. TRABAJANDO HOY\agente-administrativo-contable"

git init
git add .
git status
git commit -m "Initial commit: agente administrativo-contable con dashboard y chat"

git branch -M main
git remote add origin https://github.com/TU_USUARIO/agente-administrativo-contable.git
git push -u origin main
```

Reemplaza `TU_USUARIO` por tu usuario de GitHub.

---

## Después del push

Quien clone el repo debe:

```powershell
git clone https://github.com/TU_USUARIO/agente-administrativo-contable.git
cd agente-administrativo-contable
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Ver `EJECUTAR.md` para correr agente y dashboard.

---

## Desplegar en Railway (opcional)

1. Railway → New Project → Deploy from GitHub
2. Conectar el repo
3. Agregar variables de `.env.example` en **Variables** (con valores reales)
4. Start command: `python agente.py` (ver `railway.json`)
5. Segundo servicio para dashboard: `streamlit run dashboard/app.py --server.port $PORT --server.address 0.0.0.0`
