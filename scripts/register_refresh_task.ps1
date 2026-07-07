# Registers (or updates) the weekly ClutchCast refresh in Windows Task Scheduler.
# Run once:  powershell -ExecutionPolicy Bypass -File scripts\register_refresh_task.ps1
# Remove:    Unregister-ScheduledTask -TaskName "ClutchCast Weekly Refresh" -Confirm:$false

$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$script = Join-Path $projectRoot "src\refresh_all.py"

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$script`"" -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 6:00AM
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -RestartCount 1 -RestartInterval (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName "ClutchCast Weekly Refresh" `
    -Description "Downloads new NBA games, retrains the ClutchCast models, refreshes site data, and pushes to deploy. Logs to reports\refresh_logs." `
    -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Registered 'ClutchCast Weekly Refresh' - Mondays 6:00 AM (runs when the PC is next awake if missed)."
Write-Host "Logs land in reports\refresh_logs\. Test it now with:"
Write-Host "  .venv\Scripts\python.exe src\refresh_all.py --skip-push"
