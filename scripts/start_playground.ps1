$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& .\.venv\Scripts\python.exe -m uvicorn backend.playground:app --host 127.0.0.1 --port 8001
