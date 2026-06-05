$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$env:PYTHONPATH = Join-Path $ProjectRoot "src"

E:\Python312\python.exe -m gansu_downloader.cli `
  --estimate-csv E:\yanjiusheng\gansu_arcgis_ready\gansu_5m_county_estimate.csv `
  --out-dir E:\yanjiusheng\gansu_5m_whole_downloads `
  --work-dir E:\yanjiusheng\gansu_5m_work `
  --workers 16 `
  --max-tiles-per-chunk 2000 `
  --order largest-first
