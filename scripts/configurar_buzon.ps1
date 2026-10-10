# ============================================================
# Conecta un buzón de correo a Shaki (solo lectura).
# Guarda la contraseña en el .env de ESTE computador (nunca en GitHub).
# Uso:
#   powershell -ExecutionPolicy Bypass -File scripts\configurar_buzon.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\configurar_buzon.ps1 -Correo gerencia@viaindustrial.com
# Gmail: use una CONTRASEÑA DE APLICACIÓN (myaccount.google.com/apppasswords), no la clave normal.
# ============================================================
param([string]$Correo = "")
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$envPath = Join-Path $raiz ".env"
if (-not (Test-Path $envPath)) { Copy-Item (Join-Path $raiz ".env.example") $envPath }
if (-not $Correo) { $Correo = Read-Host "¿Qué correo va a conectar? (ej. gerencia@viaindustrial.com)" }
$Correo = $Correo.Trim().ToLower()
if ($Correo -notmatch "^[^@\s]+@[^@\s]+\.[a-z]{2,}$") { Write-Error "Correo no válido"; exit 1 }
if ($Correo -like "*@gmail.com") {
    Write-Host "Es Gmail: pegue la CONTRASEÑA DE APLICACIÓN de 16 letras (no la clave normal)." -ForegroundColor Yellow
}
$seguro = Read-Host "Contraseña de $Correo (no se verá al escribir)" -AsSecureString
$clave = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro))
if ($Correo -like "*@gmail.com") { $clave = $clave -replace '\s', '' }
$var = "CORREO_PASS_" + ($Correo.ToUpper() -replace '[^A-Z0-9]', '_')
$lineas = [System.Collections.Generic.List[string]](Get-Content $envPath -Encoding UTF8)
$i = $lineas.FindIndex([Predicate[string]] { param($l) $l -match "^\s*$var\s*=" })
if ($i -ge 0) { $lineas[$i] = "$var=$clave" } else { $lineas.Add("$var=$clave") }
Set-Content -Path $envPath -Value $lineas -Encoding UTF8
Write-Host "Contraseña guardada en .env para $Correo" -ForegroundColor Green

$py = "C:\venvs\shaki\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
Write-Host "Probando la conexión (solo lectura)..." -ForegroundColor Cyan
& $py -c "from dotenv import load_dotenv; load_dotenv(override=True); from modulos import buzones as b; b.inicializar(); bid=b.agregar_buzon('$Correo'); x=[z for z in b.listar_buzones() if z['email']=='$Correo'][0]; r=b.probar(x['id']); print('CONECTADO: ' + str(r.get('mensajes')) + ' correos en la bandeja' if r['ok'] else 'ERROR: ' + r['error'])"
Write-Host "Reinicie Shaki para que empiece a leer este buzón cada 10 minutos."
