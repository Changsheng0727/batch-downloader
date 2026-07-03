# Batch Imagery Downloader

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![ArcGIS](https://img.shields.io/badge/ArcGIS-Desktop%2010.x-2C7AC3)](https://www.esri.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)](https://www.microsoft.com/windows/)

Batch-download Esri Wayback World Imagery tiles, mosaic them into GeoTIFF rasters, and clip each raster with ArcGIS/ArcPy.

The examples in this repository use Gansu county data because that was the original production workflow, but the pipeline itself is generic: if you can provide an estimate CSV and boundary features, you can reuse it for other provinces, cities, counties, or custom regions.

- Resumable chunked downloads for large regions
- Concurrent tile fetching with connection reuse and local caching
- ArcGIS clipping and safe final-raster replacement
- JSON config support for repeatable batch jobs

## Table of Contents

- [Why This Project](#why-this-project)
- [Workflow](#workflow)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [CLI Usage](#cli-usage)
- [Output Layout](#output-layout)
- [Project Structure](#project-structure)
- [Operational Notes](#operational-notes)
- [FAQ](#faq)

## Why This Project

This repository is designed for long-running imagery jobs where a simple download script is not enough.

Key improvements in the current implementation:

- Internal chunk planning prevents extremely large regions from becoming one fragile job.
- Completed clipped chunks are reused automatically on reruns unless `--redo` is set.
- HTTP sessions are reused per worker thread, which improves throughput for large tile batches.
- Final GeoTIFF outputs are replaced only after a successful merge, which avoids corrupting the previous finished result during retries.
- ArcGIS clipping disables unnecessary raster pyramids and statistics during intermediate work to reduce overhead.

## Workflow

```text
Estimate CSV
  -> select region IDs
  -> split large regions into internal chunks
  -> download tiles with cache + concurrency
  -> mosaic each chunk into a raw TIFF
  -> clip each chunk with ArcGIS
  -> merge chunk outputs into one final GeoTIFF
  -> write status CSV
```

## Quick Start

### 1. Install dependencies

```powershell
cd path\to\batch-downloader
python -m pip install -e .
```

### 2. Prepare a local config

```powershell
copy configs\gansu.example.json configs\gansu.local.json
notepad configs\gansu.local.json
```

At minimum, update every `CHANGE_ME` path, especially `arcgis_python`.

### 3. Preview the plan

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --dry-run
```

### 4. Run the batch job

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json
```

## Configuration

Example config:

```json
{
  "estimate_csv": "CHANGE_ME/path/to/region_estimate.csv",
  "out_dir": "CHANGE_ME/path/to/final_geotiffs",
  "work_dir": "CHANGE_ME/path/to/work_dir",
  "reference_dir": "CHANGE_ME/path/to/reference_dir_with_web_mercator_prj",
  "arcgis_python": "CHANGE_ME/path/to/ArcGIS/python.exe",
  "resolution": 5.0,
  "wayback_id": "58924",
  "workers": 12,
  "max_tiles_per_chunk": 2000,
  "order": "largest-first",
  "status_csv_name": "download_status.csv",
  "redo": false,
  "keep_parts": false,
  "dry_run": false
}
```

Important fields:

| Field | Required | Description |
| --- | --- | --- |
| `estimate_csv` | Yes | CSV containing region IDs, tile bounds, and output naming fields |
| `out_dir` | Yes | Directory for final clipped GeoTIFF outputs |
| `work_dir` | Yes | Directory for chunk outputs, raw mosaics, and caches |
| `reference_dir` | Yes | Directory containing `web_mercator_aux_sphere.prj` |
| `arcgis_python` | Yes | ArcGIS Desktop / ArcPy Python executable |
| `resolution` | No | Target meters per pixel, default `5.0` |
| `wayback_id` | No | Esri Wayback imagery version, default `58924` |
| `workers` | No | Concurrent tile download workers, default `12` |
| `max_tiles_per_chunk` | No | Maximum tiles per internal chunk |
| `order` | No | Processing order: `id` or `largest-first` |
| `redo` | No | Force rebuild even if finished outputs already exist |
| `keep_parts` | No | Keep intermediate clipped chunks after final merge |
| `dry_run` | No | Only print the plan without downloading |

## CLI Usage

Run all configured regions:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json
```

Run selected region IDs:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 1,11,18
```

Run an ID range:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 1-10
```

Force a rebuild:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 48 --redo
```

## Output Layout

Final outputs:

```text
path\to\final_geotiffs\
  region_001_5m_clipped.tif
  region_002_5m_clipped.tif
  download_status.csv
```

Working directory:

```text
path\to\work_dir\
  raw\
  region_001\
  region_001_part_0001_clipped.tif
  region_001_part_0002_clipped.tif
```

Actual file prefixes depend on the `ascii` field in your estimate CSV.

## Project Structure

```text
batch-downloader/
  configs/
    gansu.example.json
  scripts/
    run_gansu_example.ps1
  src/gansu_downloader/
    arcgis.py      # ArcGIS clipping, mosaic, PRJ generation
    batch.py       # Batch orchestration
    cli.py         # CLI entry point
    estimates.py   # Estimate CSV parsing and chunk planning
    files.py       # Raster family copy/move/delete helpers
    status.py      # Status CSV writer
    tiles.py       # Tile math, HTTP download, chunk mosaic
  tests/
    test_estimates.py
    test_files.py
```

## Operational Notes

- This tool is designed for Windows because ArcGIS Desktop / ArcPy is part of the workflow.
- Generated imagery, caches, ArcGIS workspaces, and logs can consume large amounts of disk space.
- Do not commit downloaded rasters or temporary GIS outputs to Git.
- If a batch is interrupted, rerunning without `--redo` will reuse finished clipped chunks when available.
- If you want the previous final GeoTIFF to remain untouched until a new merge succeeds, keep using the default behavior in this version.

## FAQ

### Why does the package name still contain `gansu`?

The first production dataset for this tool was Gansu county imagery. The module name stayed stable so older scripts would not break, but the workflow itself is not Gansu-specific.

### Do I need `reference_dir` for every province?

No. It only needs to provide `web_mercator_aux_sphere.prj`, which is shared by the Web Mercator workflow.

### What does `--redo` do?

It forces the downloader to rebuild outputs even if clipped chunk files or final rasters already exist.

## Contact

If you run into a problem, open a GitHub issue or contact:

`2821452633@qq.com`
