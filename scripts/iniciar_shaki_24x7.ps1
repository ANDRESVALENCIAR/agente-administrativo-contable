# ============================================================
# Shaki 24/7 — inicia agente (alertas) + panel + túnel público
# Se puede correr varias veces: solo arranca lo que no esté corriendo.
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\iniciar_shaki_24x7.ps1
# ============================================================
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$logs = Join-Path $raiz "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# Python: entorno corto (rutas largas de Windows) > .venv > python del sistema
$py = @("C:\venvs\shaki\Scripts\python.exe", (Join-Path $raiz ".venv\Scripts\python.exe")) |
      Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $py) { $py = (Get-Command python).Source }

# Leer .env (solo lo que este script necesita)
$envVars = @{}
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$') { $envVars[$matches[1]] = $matches[2].Trim('"', "'") }
    }
}
$puerto = 8501

function Corriendo($patron) {
    @(Get-CimInstance Win32_Process -Filter "Name like 'python%' or Name like 'ngrok%'" |
      Where-Object { $_.CommandLine -like "*$patron*" }).Count -gt 0
}

# 1) Túnel público estable para el botón "Ya lo pagué" (ngrok, dominio estático gratuito)
$dominio = $envVars["NGROK_DOMAIN"]
if ($dominio) {
    $env:APP_PUBLIC_URL = "https://$dominio"   # tiene prioridad sobre .env para los procesos hijos
    $ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
    if (-not $ngrok) {
        Write-Warning "NGROK_DOMAIN está en .env pero ngrok no está instalado (winget install ngrok.ngrok)."
    } elseif (-not (Corriendo "--url=$dominio")) {
        Start-Process -FilePath $ngrok.Source -ArgumentList "http", "--url=$dominio", "$puerto", "--log=stdout" `
            -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logs "ngrok.log")
        Write-Host "Túnel: https://$dominio"
    }
}

# 2) Agente (programador: alertas 24h 08:00 y 16:30, lectura del Excel 07:30)
if (-not (Corriendo "agente.py")) {
    Start-Process -FilePath $py -ArgumentList "agente.py" -WorkingDirectory $raiz -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "agente.out.log") -RedirectStandardError (Join-Path $logs "agente.err.log")
    Write-Host "Agente iniciado"
} else { Write-Host "Agente ya estaba corriendo" }

# 3) Panel (donde abre el botón "Ya lo pagué")
if (-not (Corriendo "streamlit run dashboard")) {
    Start-Process -FilePath $py -ArgumentList "-m", "streamlit", "run", "dashboard/app.py", "--server.port", "$puerto",
        "--server.headless", "true" -WorkingDirectory $raiz -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs "panel.out.log") -RedirectStandardError (Join-Path $logs "panel.err.log")
    Write-Host "Panel iniciado en http://localhost:$puerto"
} else { Write-Host "Panel ya estaba corriendo" }
