# ============================================================
# Registra en Windows una tarea que mantiene Shaki encendido:
#  - al iniciar sesión
#  - y cada 30 minutos verifica que sigan corriendo (si algo se cerró, lo vuelve a abrir)
# Correr UNA vez:  powershell -ExecutionPolicy Bypass -File scripts\instalar_inicio_automatico.ps1
# Para quitarlo:   Unregister-ScheduledTask -TaskName "Shaki 24x7" -Confirm:$false
# ============================================================
$script = Join-Path $PSScriptRoot "iniciar_shaki_24x7.ps1"
$accion = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$alIniciar = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$cada30 = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(6) `
    -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)
$ajustes = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName "Shaki 24x7" -Action $accion -Trigger @($alIniciar, $cada30) `
    -Settings $ajustes -Description "Agente Admin Shaki: alertas de pago 24h y panel" -Force | Out-Null
Write-Host "Listo: 'Shaki 24x7' quedó en el Programador de tareas de Windows."
Start-ScheduledTask -TaskName "Shaki 24x7"
Write-Host "Shaki iniciado. Logs en la carpeta logs\"
