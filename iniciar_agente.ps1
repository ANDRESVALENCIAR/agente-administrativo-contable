# Inicia el agente autonomo (backend)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creando entorno virtual..."
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt -q
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}

Write-Host "Iniciando agente autonomo (Ctrl+C para detener)..."
.\.venv\Scripts\python.exe agente.py
