# Inicia el dashboard Streamlit y abre el navegador
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creando entorno virtual..."
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt -q
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creado .env desde .env.example (modo demo)"
}

Write-Host "Iniciando dashboard en http://localhost:8501 ..."
Start-Process "http://localhost:8501"
.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py --server.port 8501
