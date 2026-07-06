# Batch Imagery Downloader

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![ArcGIS](https://img.shields.io/badge/ArcGIS-Desktop%2010.x-2C7AC3)](https://www.esri.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)](https://www.microsoft.com/windows/)

Batch-download Esri Wayback World Imagery tiles, mosaic them into GeoTIFF rasters, and clip each raster with ArcGIS/ArcPy.

The examples in this repository use Gansu county data because that was the original production workflow, but the pipeline itself is generic. In the current version you can either reuse a prepared estimate CSV or point the tool at one polygon boundary dataset and let it auto-generate the estimate CSV for you.

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
- Downloaded tiles are now kept in a shared cache under `work_dir\tile_cache`, so reruns and neighboring regions can reuse them automatically.
- Final GeoTIFF outputs are replaced only after a successful merge, which avoids corrupting the previous finished result during retries.
- ArcGIS clipping disables unnecessary raster pyramids and statistics during intermediate work to reduce overhead.
- A single boundary feature class can now drive the whole job: the tool auto-builds the estimate CSV, defaults `work_dir`, and can auto-detect ArcGIS Python on common Windows installs.

## Workflow

```text
Boundary source or estimate CSV
  -> auto-build estimate CSV when needed
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

At minimum, update the `boundary_source` and `out_dir` paths. If ArcGIS Python is installed in a standard location, the CLI can usually detect it automatically, and common boundary fields such as `PAC`, `NAME`, or `ascii` can often be inferred as well.

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
  "boundary_source": "CHANGE_ME/path/to/county_boundaries.shp",
  "out_dir": "CHANGE_ME/path/to/final_geotiffs",
  "resolution": 5.0,
  "wayback_id": "58924",
  "workers": 12,
  "max_tiles_per_chunk": 2000,
  "order": "largest-first",
  "status_csv_name": "download_status.csv",
  "refresh_estimates": false,
  "redo": false,
  "keep_parts": false,
  "dry_run": false
}
```

Important fields:

| Field | Required | Description |
| --- | --- | --- |
| `boundary_source` | Yes, unless `estimate_csv` is provided | Polygon feature class / shapefile used to auto-build the estimate CSV |
| `estimate_csv` | Yes, unless `boundary_source` is provided | Existing CSV containing region IDs, tile bounds, clip source, and output naming fields |
| `id_field` | No | Numeric unique ID field in the boundary dataset; auto-detected when omitted |
| `name_field` | No | Display name field in the boundary dataset; auto-detected when omitted |
| `ascii_field` | No | Output filename stem field; auto-detected when omitted, then falls back to `region_001` style names if needed |
| `out_dir` | Yes | Directory for final clipped GeoTIFF outputs |
| `work_dir` | No | Directory for chunk outputs, raw mosaics, the shared tile cache, and the generated estimate CSV; defaults to `out_dir\_work` |
| `reference_dir` | No | Optional directory containing `web_mercator_aux_sphere.prj`; if omitted, the tool generates the PRJ file with ArcPy |
| `arcgis_python` | No | ArcGIS Desktop / ArcPy Python executable; auto-detected on common Windows installs when omitted |
| `resolution` | No | Target meters per pixel, default `5.0` |
| `wayback_id` | No | Esri Wayback imagery version, default `58924` |
| `workers` | No | Concurrent tile download workers, default `12` |
| `max_tiles_per_chunk` | No | Maximum tiles per internal chunk |
| `order` | No | Processing order: `id` or `largest-first` |
| `refresh_estimates` | No | Rebuild the generated estimate CSV from the boundary source before running |
| `redo` | No | Force rebuild even if finished outputs already exist |
| `keep_parts` | No | Keep intermediate clipped chunks after final merge |
| `dry_run` | No | Only print the plan without downloading |

If you use `boundary_source`, the generated estimate CSV is written to `work_dir\region_estimate.generated.csv` and reused on later runs unless `--refresh-estimates` is set.

## CLI Usage

Run all configured regions:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json
```

Run without a hand-made estimate CSV:

```powershell
python -m gansu_downloader.cli --boundary-source D:\data\counties.shp --out-dir D:\imagery\out
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

Refresh the auto-generated estimate CSV before running:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --refresh-estimates
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
  tile_cache\
  region_001_part_0001_clipped.tif
  region_001_part_0002_clipped.tif
```

Actual file prefixes depend on the `ascii` field in your estimate CSV. If that field is missing or unusable, the downloader falls back to `region_001`, `region_002`, and so on.

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
    settings.py    # Config defaults and ArcGIS Python detection
    status.py      # Status CSV writer
    tiles.py       # Tile math, HTTP download, chunk mosaic
  tests/
    test_arcgis.py
    test_estimates.py
    test_tiles.py
    test_files.py
```

## Operational Notes

- This tool is designed for Windows because ArcGIS Desktop / ArcPy is part of the workflow.
- Generated imagery, caches, ArcGIS workspaces, and logs can consume large amounts of disk space.
- Do not commit downloaded rasters or temporary GIS outputs to Git.
- If a batch is interrupted, rerunning without `--redo` will reuse finished clipped chunks when available.
- The shared tile cache under `work_dir\tile_cache` is intentionally persistent; delete it manually when you want to reclaim space or force a cold download.
- If you want the previous final GeoTIFF to remain untouched until a new merge succeeds, keep using the default behavior in this version.

## FAQ

### Why does the package name still contain `gansu`?

The first production dataset for this tool was Gansu county imagery. The module name stayed stable so older scripts would not break, but the workflow itself is not Gansu-specific.

### Do I need `reference_dir` for every province?

No. It is optional. If you do not provide it, the tool writes `web_mercator_aux_sphere.prj` into the work directory through ArcPy.

### What is the minimum input now?

Usually just one polygon boundary dataset plus `out_dir`. When you point the CLI at `boundary_source`, it can auto-build the estimate CSV, auto-detect boundary fields, default `work_dir`, and often auto-detect `arcgis_python`.

### What does `--redo` do?

It forces the downloader to rebuild outputs even if clipped chunk files or final rasters already exist.

## Contact

If you run into a problem, open a GitHub issue or contact:

`2821452633@qq.com`
