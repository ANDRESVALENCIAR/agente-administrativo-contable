# Actualiza Shaki a la última versión de GitHub y lo vuelve a abrir.
# Uso (desde cualquier carpeta):
#   powershell -ExecutionPolicy Bypass -File "<carpeta de Shaki>\scripts\actualizar_shaki.ps1"
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
Write-Host "Cerrando Shaki si estaba abierto..." -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match "streamlit" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Write-Host "Trayendo la última versión..." -ForegroundColor Cyan
git pull
$py = "C:\venvs\shaki\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
Write-Host "Revisando librerías nuevas..." -ForegroundColor Cyan
& $py -m pip install -q rapidfuzz 2>$null
Write-Host "Abriendo Shaki en http://localhost:8501 (no cierre esta ventana)" -ForegroundColor Green
& $py -m streamlit run dashboard/app.py --server.port 8501
