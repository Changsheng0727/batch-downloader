from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def _run_temp_arcgis_script(arcgis_python: Path, source: str, args: list[str], prefix: str) -> None:
    fd, script_path = tempfile.mkstemp(prefix=prefix, suffix=".py")
    os.close(fd)
    try:
        Path(script_path).write_text(source, encoding="utf-8")
        subprocess.check_call([str(arcgis_python), script_path, *args])
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass


def ensure_web_mercator_prj(arcgis_python: Path, work_dir: Path, reference_dir: Path) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "web_mercator_aux_sphere.prj"
    if target.exists():
        return
    source = reference_dir / "web_mercator_aux_sphere.prj"
    if source.exists():
        shutil.copy2(source, target)
        return

    script = r'''
from __future__ import print_function
import sys
import arcpy
path = sys.argv[1]
with open(path, "w") as handle:
    handle.write(arcpy.SpatialReference(3857).exportToString())
'''
    _run_temp_arcgis_script(arcgis_python, script, [str(target)], "region_write_prj_")


def clip_with_arcgis(arcgis_python: Path, out_dir: Path, raw_tif: Path, output_base: str, clip_feature: str) -> Path:
    script = r'''
from __future__ import print_function
import os
import sys
import arcpy

out_dir, raw_tif, output_base, boundary = sys.argv[1:5]
web_mercator = arcpy.SpatialReference(3857)

arcpy.env.overwriteOutput = True
arcpy.env.parallelProcessingFactor = "0"
arcpy.DefineProjection_management(raw_tif, web_mercator)

out_tif = os.path.join(out_dir, output_base + "_clipped.tif")
if arcpy.Exists(out_tif):
    arcpy.Delete_management(out_tif)

arcpy.Clip_management(
    raw_tif,
    "#",
    out_tif,
    boundary,
    "0",
    "ClippingGeometry",
    "NO_MAINTAIN_EXTENT",
)
print(out_tif)
'''
    _run_temp_arcgis_script(
        arcgis_python,
        script,
        [str(out_dir), str(raw_tif), output_base, clip_feature],
        "region_arcgis_clip_",
    )
    return out_dir / f"{output_base}_clipped.tif"


def mosaic_to_whole(arcgis_python: Path, parts: list[Path], out_dir: Path, out_name: str) -> None:
    script = r'''
from __future__ import print_function
import os
import sys
import arcpy

out_dir = sys.argv[1]
out_name = sys.argv[2]
parts = sys.argv[3:]
out_tif = os.path.join(out_dir, out_name)

arcpy.env.overwriteOutput = True
arcpy.env.compression = "LZW"
arcpy.env.pyramid = "NONE"
arcpy.env.rasterStatistics = "NONE"

if arcpy.Exists(out_tif):
    arcpy.Delete_management(out_tif)

spatial_ref = arcpy.Describe(parts[0]).spatialReference
arcpy.MosaicToNewRaster_management(
    parts,
    out_dir,
    out_name,
    spatial_ref,
    "8_BIT_UNSIGNED",
    "",
    3,
    "LAST",
    "FIRST",
)
print(out_tif)
'''
    _run_temp_arcgis_script(
        arcgis_python,
        script,
        [str(out_dir), out_name, *(str(part) for part in parts)],
        "region_mosaic_whole_",
    )
