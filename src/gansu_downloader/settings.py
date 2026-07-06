from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def default_work_dir(out_dir: Path, work_dir: Path | None) -> Path:
    return work_dir or (out_dir / "_work")


def default_generated_estimate_csv(work_dir: Path, estimate_csv: Path | None) -> Path:
    return estimate_csv or (work_dir / "region_estimate.generated.csv")


def default_tile_cache_dir(work_dir: Path) -> Path:
    return work_dir / "tile_cache"


def current_python_has_arcpy() -> bool:
    return importlib.util.find_spec("arcpy") is not None


def arcgis_python_candidates() -> list[Path]:
    candidates: list[Path] = []
    if current_python_has_arcpy():
        candidates.append(Path(sys.executable))

    env_candidates = [
        os.environ.get("ARCGIS_PYTHON"),
        os.environ.get("ARCPY_PYTHON"),
    ]
    candidates.extend(Path(value) for value in env_candidates if value)

    desktop_versions = ["10.8", "10.7", "10.6", "10.5", "10.4", "10.3", "10.2", "10.1", "10.0"]
    for version in desktop_versions:
        candidates.append(Path(rf"C:\Python27\ArcGIS{version}\python.exe"))

    candidates.append(Path(r"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe"))
    candidates.append(Path(r"C:\Program Files (x86)\ArcGIS\Desktop10.8\ArcPy\python.exe"))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def detect_arcgis_python(explicit: Path | None = None) -> Path | None:
    if explicit:
        return explicit
    for candidate in arcgis_python_candidates():
        if candidate.exists():
            return candidate
    return None
