from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .files import move_raster_family


@dataclass
class EstimateCsvBuildResult:
    path: Path
    id_field: str
    name_field: str | None
    ascii_field: str | None
    row_count: int


def _run_temp_arcgis_script(arcgis_python: Path, source: str, args: list[str], prefix: str) -> str:
    fd, script_path = tempfile.mkstemp(prefix=prefix, suffix=".py")
    os.close(fd)
    try:
        Path(script_path).write_text(source, encoding="utf-8")
        output = subprocess.check_output([str(arcgis_python), script_path, *args])
        return output.decode("utf-8", "replace").strip()
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass


def build_estimate_csv(
    arcgis_python: Path,
    boundary_source: Path,
    estimate_csv: Path,
    id_field: str | None,
    name_field: str | None,
    ascii_field: str | None,
    resolution: float,
) -> EstimateCsvBuildResult:
    script = r'''
from __future__ import print_function
import json
import math
import re
import sys
import arcpy

boundary, id_field, name_field, ascii_field, resolution = sys.argv[1:6]
try:
    basestring
except NameError:
    basestring = str
    unicode = str

requested_id_field = id_field or None
id_field = id_field or None
name_field = name_field or None
ascii_field = ascii_field or None
resolution = float(resolution)
ORIGIN_SHIFT = 20037508.342789244
INITIAL_RESOLUTION = 156543.03392804097
TILE_SIZE = 256

def target_zoom(resolution_m):
    zoom = int(math.ceil(math.log(INITIAL_RESOLUTION / resolution_m, 2)))
    return max(0, min(23, zoom))

def sanitize_output_stem(area_id, preferred):
    text = preferred or u""
    if not isinstance(text, unicode):
        text = unicode(text)
    text = text.strip()
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return text or ("region_%03d" % area_id)

def web_mercator_to_lonlat(x, y):
    lon = (x / ORIGIN_SHIFT) * 180.0
    lat = (y / ORIGIN_SHIFT) * 180.0
    lat = 180.0 / math.pi * (2.0 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
    return lon, lat

def extent_to_tile_range(extent, zoom):
    span = TILE_SIZE * (INITIAL_RESOLUTION / (2 ** zoom))
    max_index = (2 ** zoom) - 1
    epsilon = span / 1000000.0
    col_min = int(math.floor((extent.XMin + ORIGIN_SHIFT) / span))
    col_max = int(math.floor(((extent.XMax - epsilon) + ORIGIN_SHIFT) / span))
    row_min = int(math.floor((ORIGIN_SHIFT - extent.YMax) / span))
    row_max = int(math.floor((ORIGIN_SHIFT - (extent.YMin + epsilon)) / span))
    col_min = max(0, min(max_index, col_min))
    col_max = max(0, min(max_index, col_max))
    row_min = max(0, min(max_index, row_min))
    row_max = max(0, min(max_index, row_max))
    return col_min, col_max, row_min, row_max

def make_where(boundary_path, field_name, raw_value):
    field_sql = arcpy.AddFieldDelimiters(boundary_path, field_name)
    if isinstance(raw_value, basestring):
        return "%s = '%s'" % (field_sql, raw_value.replace("'", "''"))
    return "%s = %s" % (field_sql, raw_value)

def resolve_requested_field(field_name, field_by_lower, label):
    if not field_name:
        return None
    field = field_by_lower.get(field_name.lower())
    if field is None:
        raise RuntimeError("Boundary source is missing requested %s field: %s" % (label, field_name))
    return field.name

def is_numeric_field(field):
    return field.type in ("OID", "SmallInteger", "Integer", "Single", "Double")

def is_string_field(field):
    return field.type in ("String", "Guid")

def choose_by_names(field_by_lower, names, predicate):
    for name in names:
        field = field_by_lower.get(name.lower())
        if field and predicate(field):
            return field.name
    return None

def auto_detect_id_field(fields, field_by_lower, oid_field_name):
    field_name = choose_by_names(
        field_by_lower,
        ["pac", "xzqdm", "adcode", "countycode", "district_id", "region_id", "county_id", "id", "code"],
        is_numeric_field,
    )
    if field_name:
        return field_name
    if oid_field_name:
        oid_field = field_by_lower.get(oid_field_name.lower())
        if oid_field and is_numeric_field(oid_field):
            return oid_field.name
    for field in fields:
        if is_numeric_field(field):
            return field.name
    return None

def auto_detect_name_field(field_by_lower):
    return choose_by_names(
        field_by_lower,
        ["county", "name", "name_cn", "fullname", "full_name", "district", "city", "region", "xian", "mc"],
        is_string_field,
    )

def auto_detect_ascii_field(field_by_lower, fallback_name_field):
    field_name = choose_by_names(
        field_by_lower,
        ["ascii", "ascii_name", "name_en", "en_name", "pinyin", "filename", "file_name", "slug"],
        is_string_field,
    )
    return field_name or fallback_name_field

fields_meta = list(arcpy.ListFields(boundary))
field_by_lower = dict((field.name.lower(), field) for field in fields_meta)
description = arcpy.Describe(boundary)
oid_field_name = getattr(description, "OIDFieldName", None)

id_field = resolve_requested_field(id_field, field_by_lower, "id") or auto_detect_id_field(fields_meta, field_by_lower, oid_field_name)
if id_field is None:
    raise RuntimeError("Could not auto-detect a usable numeric id field from the boundary source.")
name_field = resolve_requested_field(name_field, field_by_lower, "name") or auto_detect_name_field(field_by_lower)
ascii_field = resolve_requested_field(ascii_field, field_by_lower, "ascii") or auto_detect_ascii_field(field_by_lower, name_field)

zoom = target_zoom(resolution)
fields = [id_field, "SHAPE@"]
if name_field:
    fields.append(name_field)
if ascii_field and ascii_field not in fields:
    fields.append(ascii_field)

sr_3857 = arcpy.SpatialReference(3857)
source_path = description.catalogPath
rows = []
used_stems = set()
seen_ids = set()
for values in arcpy.da.SearchCursor(boundary, fields):
    record = dict(zip(fields, values))
    raw_id = record[id_field]
    area_id = int(raw_id)
    if area_id in seen_ids:
        if requested_id_field:
            raise RuntimeError("Requested id field '%s' contains duplicate values: %s" % (id_field, area_id))
        raise RuntimeError("Auto-detected id field '%s' contains duplicate values: %s. Provide --id-field to choose a different field." % (id_field, area_id))
    seen_ids.add(area_id)
    geometry = record["SHAPE@"]
    geometry_3857 = geometry.projectAs(sr_3857)
    extent_3857 = geometry_3857.extent
    col_min, col_max, row_min, row_max = extent_to_tile_range(extent_3857, zoom)
    tile_count = (col_max - col_min + 1) * (row_max - row_min + 1)
    pixel_width = (col_max - col_min + 1) * TILE_SIZE
    pixel_height = (row_max - row_min + 1) * TILE_SIZE
    min_lon, min_lat = web_mercator_to_lonlat(extent_3857.XMin, extent_3857.YMin)
    max_lon, max_lat = web_mercator_to_lonlat(extent_3857.XMax, extent_3857.YMax)
    county = record.get(name_field, u"") if name_field else u""
    stem = sanitize_output_stem(area_id, record.get(ascii_field, county) if ascii_field else county)
    if stem in used_stems:
        stem = "%s_%03d" % (stem, area_id)
    used_stems.add(stem)
    rows.append(
        {
            "id": area_id,
            "county": county,
            "ascii": stem,
            "feature_class": source_path,
            "clip_where": make_where(source_path, id_field, raw_id),
            "col_min": col_min,
            "col_max": col_max,
            "row_min": row_min,
            "row_max": row_max,
            "tile_count": tile_count,
            "pixel_width": pixel_width,
            "pixel_height": pixel_height,
            "xmin": min_lon,
            "ymin": min_lat,
            "xmax": max_lon,
            "ymax": max_lat,
            "approx_uncompressed_rgb_gb": (pixel_width * pixel_height * 3.0) / (1024.0 ** 3),
        }
    )

payload = json.dumps(
    {
        "meta": {
            "id_field": id_field,
            "name_field": name_field,
            "ascii_field": ascii_field,
            "row_count": len(rows),
        },
        "rows": rows,
    },
    ensure_ascii=False,
)
if sys.version_info[0] < 3:
    sys.stdout.write(payload.encode("utf-8"))
else:
    sys.stdout.write(payload)
'''
    output = _run_temp_arcgis_script(
        arcgis_python,
        script,
        [str(boundary_source), id_field or "", name_field or "", ascii_field or "", str(resolution)],
        "region_build_estimates_",
    )
    payload_text = output.splitlines()[-1] if output else "{}"
    payload = json.loads(payload_text)
    if isinstance(payload, list):
        meta = {
            "id_field": id_field or "id",
            "name_field": name_field,
            "ascii_field": ascii_field,
            "row_count": len(payload),
        }
        rows = payload
    else:
        meta = payload.get("meta", {})
        rows = payload.get("rows", [])
    estimate_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "county",
        "ascii",
        "feature_class",
        "clip_where",
        "col_min",
        "col_max",
        "row_min",
        "row_max",
        "tile_count",
        "pixel_width",
        "pixel_height",
        "xmin",
        "ymin",
        "xmax",
        "ymax",
        "approx_uncompressed_rgb_gb",
    ]
    with estimate_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return EstimateCsvBuildResult(
        path=estimate_csv,
        id_field=str(meta.get("id_field") or id_field or "id"),
        name_field=str(meta["name_field"]) if meta.get("name_field") is not None else None,
        ascii_field=str(meta["ascii_field"]) if meta.get("ascii_field") is not None else None,
        row_count=int(meta.get("row_count", len(rows))),
    )


def ensure_web_mercator_prj(arcgis_python: Path, work_dir: Path, reference_dir: Path | None) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "web_mercator_aux_sphere.prj"
    if target.exists():
        return
    if reference_dir:
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


def clip_with_arcgis(
    arcgis_python: Path,
    out_dir: Path,
    raw_tif: Path,
    output_base: str,
    clip_feature: str,
    clip_where: str = "",
) -> Path:
    script = r'''
from __future__ import print_function
import os
import sys
import arcpy

out_dir, raw_tif, output_base, boundary, clip_where = sys.argv[1:6]
web_mercator = arcpy.SpatialReference(3857)

arcpy.env.overwriteOutput = True
arcpy.env.parallelProcessingFactor = "0"
arcpy.env.compression = "LZW"
arcpy.env.pyramid = "NONE"
arcpy.env.rasterStatistics = "NONE"
arcpy.DefineProjection_management(raw_tif, web_mercator)

out_tif = os.path.join(out_dir, output_base + "_clipped.tif")
if arcpy.Exists(out_tif):
    arcpy.Delete_management(out_tif)

boundary_input = boundary
temp_layer = None
if clip_where:
    temp_layer = "clip_boundary_%s" % output_base
    if arcpy.Exists(temp_layer):
        arcpy.Delete_management(temp_layer)
    arcpy.MakeFeatureLayer_management(boundary, temp_layer, clip_where)
    boundary_input = temp_layer

arcpy.Clip_management(
    raw_tif,
    "#",
    out_tif,
    boundary_input,
    "0",
    "ClippingGeometry",
    "NO_MAINTAIN_EXTENT",
)
if temp_layer and arcpy.Exists(temp_layer):
    arcpy.Delete_management(temp_layer)
print(out_tif)
'''
    _run_temp_arcgis_script(
        arcgis_python,
        script,
        [str(out_dir), str(raw_tif), output_base, clip_feature, clip_where],
        "region_arcgis_clip_",
    )
    return out_dir / f"{output_base}_clipped.tif"


def mosaic_to_whole(arcgis_python: Path, parts: list[Path], out_dir: Path, out_name: str) -> Path:
    script = r'''
from __future__ import print_function
import os
import sys
import arcpy

out_dir = sys.argv[1]
out_name = sys.argv[2]
parts = sys.argv[3:]
temp_name = out_name.rsplit(".", 1)[0] + "_building.tif"
out_tif = os.path.join(out_dir, temp_name)

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
    output = _run_temp_arcgis_script(
        arcgis_python,
        script,
        [str(out_dir), out_name, *(str(part) for part in parts)],
        "region_mosaic_whole_",
    )
    temp_tif = Path(output.splitlines()[-1])
    final_tif = out_dir / out_name
    move_raster_family(temp_tif, final_tif)
    return final_tif
