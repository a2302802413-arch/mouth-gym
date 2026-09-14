$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$url = "http://127.0.0.1:8000"
[System.Diagnostics.Process]::Start($url) | Out-Null
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
