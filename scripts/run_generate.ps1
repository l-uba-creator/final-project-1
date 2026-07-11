# Обёртка для запуска генератора выгрузок через Планировщик заданий Windows.
$env:PYTHONUTF8 = "1"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

& "$ProjectRoot\.venv\Scripts\python.exe" "$ProjectRoot\scripts\generate_data.py" 2>&1 |
    Out-File -FilePath "$ProjectRoot\logs\run_generate.ps1.log" -Append -Encoding utf8
