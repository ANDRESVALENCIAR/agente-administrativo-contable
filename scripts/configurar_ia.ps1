# ============================================================
# Activa la IA de Shaki (Claude). Guarda la clave de Anthropic en el .env de ESTE computador.
# La clave nunca se escribe en el chat ni se sube a GitHub (.env está ignorado).
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\configurar_ia.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\configurar_ia.ps1 -Quitar   (vuelve al modo local)
# La clave se crea en https://console.anthropic.com  ->  API Keys  ->  Create Key  (empieza por sk-ant-)
# ============================================================
param([switch]$Quitar)
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$envPath = Join-Path $raiz ".env"
if (-not (Test-Path $envPath)) { Copy-Item (Join-Path $raiz ".env.example") $envPath }
$lineas = [System.Collections.Generic.List[string]](Get-Content $envPath -Encoding UTF8)

function Poner([string]$var, [string]$valor) {
    $i = $lineas.FindIndex([Predicate[string]] { param($l) $l -match "^\s*$var\s*=" })
    if ($i -ge 0) { $lineas[$i] = "$var=$valor" } else { $lineas.Add("$var=$valor") }
}

if ($Quitar) {
    Poner "ANTHROPIC_API_KEY" ""
    Set-Content -Path $envPath -Value $lineas -Encoding UTF8
    Write-Host "IA desactivada. Shaki sigue funcionando en modo local (gratis)." -ForegroundColor Yellow
    exit 0
}

Write-Host "Pegue la clave de Anthropic (empieza por sk-ant-). No se verá al escribir." -ForegroundColor Cyan
$seguro = Read-Host "Clave" -AsSecureString
$clave = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro))
$clave = $clave.Trim()
if ($clave -notmatch "^sk-ant-") { Write-Error "Eso no parece una clave de Anthropic (debe empezar por sk-ant-)."; exit 1 }
Poner "ANTHROPIC_API_KEY" $clave
Set-Content -Path $envPath -Value $lineas -Encoding UTF8
Write-Host "Clave guardada en .env" -ForegroundColor Green

$py = "C:\venvs\shaki\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
& $py -m pip install -q --upgrade anthropic 2>$null
Write-Host "Probando la clave..." -ForegroundColor Cyan
& $py (Join-Path $raiz "scripts\probar_ia.py")
if ($LASTEXITCODE -eq 0) {
    Write-Host "Listo. Cierre Shaki y vuelva a abrirlo (actualizar_shaki.ps1) para que use la IA." -ForegroundColor Green
} else {
    Write-Host "La clave quedó guardada pero la prueba falló: revise el mensaje de arriba." -ForegroundColor Yellow
}
