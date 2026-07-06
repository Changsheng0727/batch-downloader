<a id="readme-top"></a>

# Batch Imagery Downloader

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![ArcGIS](https://img.shields.io/badge/ArcGIS-Desktop%2010.x-2C7AC3)](https://www.esri.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows&logoColor=white)](https://www.microsoft.com/windows/)
[![GitHub Issues](https://img.shields.io/github/issues/Changsheng0727/batch-downloader)](https://github.com/Changsheng0727/batch-downloader/issues)
[![GitHub Stars](https://img.shields.io/github/stars/Changsheng0727/batch-downloader?style=social)](https://github.com/Changsheng0727/batch-downloader/stargazers)

[English](README.md) | [简体中文](README.zh-CN.md)

Batch-download Esri Wayback World Imagery tiles, mosaic them into GeoTIFF rasters, and clip the finished outputs with ArcGIS/ArcPy.

This project started from a real Gansu county imagery workflow, then grew into a reusable downloader for province, city, county, and custom polygon batches. The current version can run from a minimal boundary dataset plus an output directory, auto-generate the estimate CSV, auto-detect common boundary fields, and reuse a shared tile cache across reruns.

**Links**

- Project: `https://github.com/Changsheng0727/batch-downloader`
- Issues: `https://github.com/Changsheng0727/batch-downloader/issues`

## Table of Contents

1. [About The Project](#about-the-project)
2. [Built With](#built-with)
3. [Getting Started](#getting-started)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Output Layout](#output-layout)
7. [Project Structure](#project-structure)
8. [Operational Notes](#operational-notes)
9. [Roadmap](#roadmap)
10. [Contributing](#contributing)
11. [License](#license)
12. [Contact](#contact)
13. [Acknowledgments](#acknowledgments)

## About The Project

This repository is built for long-running remote-sensing download jobs where a small one-off script stops being enough.

What it already does well:

- Splits large regions into safer internal chunks.
- Reuses completed clipped chunks unless `--redo` is set.
- Reuses HTTP sessions per worker thread for better throughput.
- Persists a shared tile cache under `work_dir\tile_cache` so reruns and neighboring regions can reuse downloaded tiles.
- Replaces final GeoTIFF outputs only after a successful merge.
- Disables unnecessary ArcGIS raster pyramids and statistics during intermediate clipping work.
- Can run directly from one polygon boundary dataset and auto-build `region_estimate.generated.csv`.
- Auto-detects common fields such as `PAC`, `XZQDM`, `NAME`, and `ascii` when possible.
- Auto-detects ArcGIS Python from common Windows install paths.

Typical workflow:

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Built With

- Python 3.10+
- ArcGIS Desktop 10.x / ArcPy
- Pillow
- Requests
- Windows

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites

- Windows machine
- ArcGIS Desktop / ArcPy runtime available locally
- Python 3.10 or newer for the CLI package

If ArcGIS Python is installed in a standard location, the downloader usually finds it automatically.

### Installation

1. Clone the repository:

```powershell
git clone https://github.com/Changsheng0727/batch-downloader.git
cd batch-downloader
```

2. Install the package in editable mode:

```powershell
python -m pip install -e .
```

3. Create a local config:

```powershell
copy configs\gansu.example.json configs\gansu.local.json
notepad configs\gansu.local.json
```

### Minimum Input

In the common case, you only need:

- `boundary_source`
- `out_dir`

When you provide `boundary_source`, the downloader can usually infer:

- `id_field`
- `name_field`
- `ascii_field`
- `work_dir`
- `arcgis_python`

<p align="right">(<a href="#readme-top">back to top</a>)</p>

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
| `estimate_csv` | Yes, unless `boundary_source` is provided | Existing estimate CSV with region bounds, clip source, and output naming fields |
| `id_field` | No | Numeric unique ID field; auto-detected when omitted |
| `name_field` | No | Display name field; auto-detected when omitted |
| `ascii_field` | No | Output filename stem field; auto-detected when omitted, then falls back to `region_001` style names |
| `out_dir` | Yes | Directory for final clipped GeoTIFF outputs |
| `work_dir` | No | Directory for raw mosaics, clipped parts, shared tile cache, and generated estimate CSV; defaults to `out_dir\_work` |
| `reference_dir` | No | Optional directory containing `web_mercator_aux_sphere.prj`; otherwise ArcPy writes it into the work directory |
| `arcgis_python` | No | ArcGIS Desktop / ArcPy Python executable; auto-detected when omitted |
| `resolution` | No | Target meters per pixel; default `5.0` |
| `wayback_id` | No | Esri Wayback imagery version; default `58924` |
| `workers` | No | Concurrent tile download workers; default `12` |
| `max_tiles_per_chunk` | No | Maximum tiles per internal chunk |
| `order` | No | Processing order: `id` or `largest-first` |
| `refresh_estimates` | No | Rebuild the generated estimate CSV before running |
| `redo` | No | Force rebuild even if outputs already exist |
| `keep_parts` | No | Keep intermediate clipped chunk files |
| `dry_run` | No | Print the plan without downloading |

If you use `boundary_source`, the generated estimate CSV is written to `work_dir\region_estimate.generated.csv` and reused on later runs unless `--refresh-estimates` is set.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

Run all configured regions:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json
```

Run from a boundary dataset without a hand-made estimate CSV:

```powershell
python -m gansu_downloader.cli --boundary-source D:\data\counties.shp --out-dir D:\imagery\out
```

Preview the full plan without downloading:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --dry-run
```

Run selected IDs:

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

Refresh the generated estimate CSV before running:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --refresh-estimates
```

PowerShell helper script:

```powershell
scripts\run_gansu_example.ps1
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

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
  region_estimate.generated.csv
```

Actual file prefixes depend on the `ascii` field in the estimate CSV. If that field is missing or unusable, the downloader falls back to `region_001`, `region_002`, and so on.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

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
    test_files.py
    test_tiles.py
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Operational Notes

- This tool is designed for Windows because ArcGIS Desktop / ArcPy is part of the workflow.
- Generated imagery, caches, ArcGIS workspaces, and logs can consume a lot of disk space.
- Do not commit downloaded rasters or temporary GIS outputs to Git.
- The shared tile cache under `work_dir\tile_cache` is intentionally persistent; delete it manually when you want to reclaim space or force a cold download.
- The package name still contains `gansu` for backward compatibility with earlier production scripts.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

- [x] Boundary-driven auto estimate CSV generation
- [x] Auto-detection for common boundary fields
- [x] ArcGIS Python auto-detection
- [x] Persistent shared tile cache
- [x] Real ArcGIS dry-run verification
- [x] Real tiny end-to-end download and clip verification
- [ ] Lower-memory mosaicking for very large regions
- [ ] Reduce ArcGIS subprocess overhead for many chunks
- [ ] Optional cache pruning / cleanup policy

See the [open issues](https://github.com/Changsheng0727/batch-downloader/issues) for future changes and bug reports.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-change`
3. Commit your changes: `git commit -m "Describe your change"`
4. Push the branch: `git push origin feature/your-change`
5. Open a Pull Request

If you are planning a bigger change, opening an issue first is a good move.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

This repository does not currently include a standalone `LICENSE` file.

If you plan to distribute or open-source the project more broadly, adding an explicit license should be the next housekeeping step.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contact

- Email: `2821452633@qq.com`
- Project Link: `https://github.com/Changsheng0727/batch-downloader`

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Acknowledgments

- [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
- [Esri Wayback World Imagery](https://livingatlas.arcgis.com/wayback/)
- ArcGIS / ArcPy production workflows used in earlier Gansu county imagery processing

<p align="right">(<a href="#readme-top">back to top</a>)</p>
