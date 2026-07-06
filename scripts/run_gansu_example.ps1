$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Config = Join-Path $ProjectRoot "configs\gansu.local.json"
if (!(Test-Path $Config)) {
  throw "Copy configs\gansu.example.json to configs\gansu.local.json, then at least fill in boundary_source and out_dir before running."
}

$env:PYTHONPATH = Join-Path $ProjectRoot "src"

python -m gansu_downloader.cli --config $Config
