# Обёртка для запуска загрузчика данных в БД через Планировщик заданий Windows.
$env:PYTHONUTF8 = "1"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

& "$ProjectRoot\.venv\Scripts\python.exe" "$ProjectRoot\scripts\load_to_db.py" 2>&1 |
    Out-File -FilePath "$ProjectRoot\logs\run_load.ps1.log" -Append -Encoding utf8
