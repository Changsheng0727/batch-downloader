# Batch Imagery Downloader

This project batch-downloads Esri Wayback World Imagery tiles, mosaics them into GeoTIFF rasters, and clips each raster to an administrative boundary with ArcGIS/ArcPy.

The current examples use Gansu Province because that was the first production dataset, but the workflow is not limited to Gansu. You can adapt it to any province, city, county set, or custom region as long as you provide:

- A region estimate CSV with tile ranges
- Boundary feature classes or shapefiles for clipping
- An ArcGIS Desktop/ArcPy Python environment
- Output and work directories

## Features

- Read tile ranges from an estimate CSV
- Select regions by ID, for example `--areas 1,11,18` or `--areas 1-10`
- Split large regions into internal chunks for download and clipping
- Reuse completed internal clipped chunks on reruns
- Merge chunks into one final GeoTIFF per region
- Download tiles concurrently with a local cache
- Write a status CSV for completed, skipped, and failed regions
- Use Gansu Province as an example dataset, while keeping the pipeline reusable for other regions

## Project Structure

```text
batch-downloader/
  src/gansu_downloader/
    arcgis.py      # ArcGIS/ArcPy clipping, mosaic, and PRJ generation
    batch.py       # Batch download workflow
    cli.py         # Command-line entry point
    estimates.py   # Estimate CSV loading and chunk planning
    status.py      # Status CSV writing
    tiles.py       # Coordinate conversion, tile download, and mosaic creation
  configs/
    gansu.example.json
  scripts/
    run_gansu_example.ps1
```

Note: module and example config names still contain `gansu` because this project was first built from a Gansu dataset. The downloader logic itself is generic.

## Environment

- Python 3.10+ for the main downloader
- ArcGIS Desktop 10.x Python 2.7, or another ArcPy-capable Python, for clipping and mosaicking
- Python packages: `requests`, `Pillow`

Install dependencies:

```powershell
cd path\to\batch-downloader
python -m pip install -r requirements.txt
```

## Configure Paths

This project does not include fixed local disk paths. Before running, copy the example config and edit every `CHANGE_ME` value, especially `arcgis_python`.

```powershell
copy configs\gansu.example.json configs\gansu.local.json
notepad configs\gansu.local.json
```

Example config fields:

```json
{
  "estimate_csv": "CHANGE_ME/path/to/region_estimate.csv",
  "out_dir": "CHANGE_ME/path/to/final_geotiffs",
  "work_dir": "CHANGE_ME/path/to/work_dir",
  "reference_dir": "CHANGE_ME/path/to/reference_dir_with_web_mercator_prj",
  "arcgis_python": "CHANGE_ME/path/to/ArcGIS/python.exe",
  "resolution": 5.0,
  "wayback_id": "58924",
  "workers": 16,
  "max_tiles_per_chunk": 2000,
  "order": "largest-first",
  "status_csv_name": "download_status.csv"
}
```

For another province or region, create your own local config with the same fields and point them to your data. `reference_dir` only needs to contain `web_mercator_aux_sphere.prj`; it is not tied to any province.

## Run

Preview the plan without downloading:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --dry-run
```

Download all configured regions:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json
```

Retry or run selected region IDs:

```powershell
python -m gansu_downloader.cli --config configs\gansu.local.json --areas 71,1,11,18,45,51,75
```

## Output

Final GeoTIFF outputs:

```text
path\to\final_geotiffs/
  region_001_5m_clipped.tif
  region_002_5m_clipped.tif
  download_status.csv
```

Internal work directory:

```text
path\to\work_dir/
  raw/
  region_001/
  region_001_part_0001_clipped.tif
```

Actual file prefixes depend on the `ascii` field in your estimate CSV.

## Notes

Downloaded rasters, tile caches, ArcGIS workspaces, and logs can be very large. Do not commit generated imagery or local data to Git. The repository `.gitignore` excludes common raster, GIS, cache, log, and output files.

## Feedback and Contact

If you run into a problem, please open a GitHub issue. You can also contact me by email:

`2821452633@qq.com`

如果使用过程中遇到问题，欢迎在 GitHub Issues 中提出，也可以通过上面的邮箱联系我。
