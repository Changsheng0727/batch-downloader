from __future__ import annotations

import shutil
from pathlib import Path


SIDE_EXTENSIONS = [".tfw", ".prj"]
TRAILING_EXTENSIONS = [".aux.xml", ".ovr", ".xml"]


def delete_raster_family(path: Path) -> None:
    base = path.with_suffix("")
    candidates = [path, *(base.with_suffix(ext) for ext in SIDE_EXTENSIONS), *(Path(str(path) + ext) for ext in TRAILING_EXTENSIONS)]
    for candidate in candidates:
        try:
            if candidate.exists():
                candidate.unlink()
        except OSError:
            pass


def copy_raster_family(src_tif: Path, dest_tif: Path) -> None:
    dest_tif.parent.mkdir(parents=True, exist_ok=True)
    temp_tif = dest_tif.with_name(f"{dest_tif.stem}.tmp_copy{dest_tif.suffix}")
    delete_raster_family(temp_tif)
    shutil.copy2(src_tif, temp_tif)
    for src_side, dest_side in [
        (src_tif.with_suffix(".tfw"), temp_tif.with_suffix(".tfw")),
        (src_tif.with_suffix(".prj"), temp_tif.with_suffix(".prj")),
        (Path(str(src_tif) + ".aux.xml"), Path(str(temp_tif) + ".aux.xml")),
        (Path(str(src_tif) + ".ovr"), Path(str(temp_tif) + ".ovr")),
        (Path(str(src_tif) + ".xml"), Path(str(temp_tif) + ".xml")),
    ]:
        if src_side.exists():
            shutil.copy2(src_side, dest_side)
    move_raster_family(temp_tif, dest_tif)


def move_raster_family(src_tif: Path, dest_tif: Path) -> None:
    delete_raster_family(dest_tif)
    dest_tif.parent.mkdir(parents=True, exist_ok=True)
    src_tif.replace(dest_tif)
    for src_side, dest_side in [
        (src_tif.with_suffix(".tfw"), dest_tif.with_suffix(".tfw")),
        (src_tif.with_suffix(".prj"), dest_tif.with_suffix(".prj")),
        (Path(str(src_tif) + ".aux.xml"), Path(str(dest_tif) + ".aux.xml")),
        (Path(str(src_tif) + ".ovr"), Path(str(dest_tif) + ".ovr")),
        (Path(str(src_tif) + ".xml"), Path(str(dest_tif) + ".xml")),
    ]:
        if src_side.exists():
            src_side.replace(dest_side)


def cleanup_dir(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
