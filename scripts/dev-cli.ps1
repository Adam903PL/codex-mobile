$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\apps\cli"
if (!(Test-Path ".venv")) {
  py -m venv .venv
}
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\devlink.exe doctor

