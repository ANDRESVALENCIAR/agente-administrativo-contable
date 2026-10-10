# ============================================================
# Configura el correo de alertas de Shaki en el .env
# Pide la contraseña de aplicación sin mostrarla en pantalla.
# Uso: powershell -ExecutionPolicy Bypass -File scripts\configurar_correo.ps1
# ============================================================
param(
    [string]$Cuenta = "shaki.admon@gmail.com",
    [string]$Destinos = ""
)
$raiz = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $raiz ".env"
if (-not (Test-Path $envPath)) { Copy-Item (Join-Path $raiz ".env.example") $envPath }

if (-not $Destinos) {
    $Destinos = Read-Host "¿A qué correo(s) llega la alerta? (separados por coma; Enter = $Cuenta)"
    if (-not $Destinos) { $Destinos = $Cuenta }
}
$seguro = Read-Host "Pegue la contraseña de aplicación de 16 letras (no se verá)" -AsSecureString
$clave = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)) -replace '\s', ''
if ($clave.Length -ne 16) { Write-Warning "La contraseña de aplicación debería tener 16 letras (tiene $($clave.Length))." }

$valores = [ordered]@{
    "SMTP_HOST"           = "smtp.gmail.com"
    "SMTP_PORT"           = "587"
    "SMTP_USER"           = $Cuenta
    "SMTP_PASSWORD"       = $clave
    "SMTP_FROM"           = $Cuenta
    "GMAIL_USER"          = $Cuenta
    "PAGOS_ALERTA_EMAILS" = $Destinos
}
$lineas = [System.Collections.Generic.List[string]](Get-Content $envPath -Encoding UTF8)
foreach ($k in $valores.Keys) {
    $i = $lineas.FindIndex([Predicate[string]] { param($l) $l -match "^\s*$k\s*=" })
    $nueva = "$k=$($valores[$k])"
    if ($i -ge 0) { $lineas[$i] = $nueva } else { $lineas.Add($nueva) }
}
Set-Content -Path $envPath -Value $lineas -Encoding UTF8

# Prueba de conexión real con Gmail (no envía nada)
try {
    $tcp = New-Object Net.Sockets.TcpClient("smtp.gmail.com", 587); $tcp.Close()
    Write-Host "Conexión con smtp.gmail.com: OK"
} catch { Write-Warning "No se pudo conectar a smtp.gmail.com:587 ($($_.Exception.Message))" }
Write-Host "Listo. Correo de alertas: $Cuenta -> $Destinos"
Write-Host "Reinicie el panel y use Pagos > Probar envío."
