<#
.SYNOPSIS
    Регистрирует в Планировщике заданий Windows две задачи автоматизации проекта:
      - RetailDataGenerate — генерация ежедневной CSV-выгрузки касс (эмуляция кассового ПО),
        каждый день, кроме воскресенья.
      - RetailDataLoad — загрузка выгрузок из data/ в PostgreSQL, каждый день.

.NOTES
    Запускать из PowerShell в корне проекта или как есть — путь к проекту
    вычисляется автоматически. Для регистрации задач обычно достаточно прав
    текущего пользователя.
#>

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

$generateAction = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ProjectRoot\scripts\run_generate.ps1`""

$loadAction = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ProjectRoot\scripts\run_load.ps1`""

# Каждый день, кроме воскресенья, в 08:00 — генерация выгрузки кассовым ПО
$generateTrigger = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek Monday, Tuesday, Wednesday, Thursday, Friday, Saturday `
    -At "08:00"

# Каждый день в 08:30 — загрузка накопленных выгрузок в БД
$loadTrigger = New-ScheduledTaskTrigger -Daily -At "08:30"

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName "RetailDataGenerate" `
    -Action $generateAction -Trigger $generateTrigger -Settings $settings `
    -Description "Генерация ежедневной CSV-выгрузки касс (эмуляция кассового ПО). Каждый день, кроме воскресенья." `
    -Force | Out-Null

Register-ScheduledTask -TaskName "RetailDataLoad" `
    -Action $loadAction -Trigger $loadTrigger -Settings $settings `
    -Description "Загрузка CSV-выгрузок из data/ в PostgreSQL. Каждый день." `
    -Force | Out-Null

Write-Host "Задачи 'RetailDataGenerate' и 'RetailDataLoad' зарегистрированы в Планировщике заданий."
Get-ScheduledTask -TaskName "RetailData*" | Select-Object TaskName, State
