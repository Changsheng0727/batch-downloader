from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .arcgis import build_estimate_csv, clip_with_arcgis, ensure_web_mercator_prj, mosaic_to_whole
from .estimates import load_estimates, parse_areas, sanitize_output_stem, split_area
from .files import copy_raster_family, delete_raster_family
from .settings import default_generated_estimate_csv, default_tile_cache_dir
from .status import write_manifest_row
from .tiles import build_mosaic_chunk, target_zoom


@dataclass
class DownloadOptions:
    estimate_csv: Path | None
    out_dir: Path
    work_dir: Path
    boundary_source: Path | None
    id_field: str | None
    name_field: str | None
    ascii_field: str | None
    reference_dir: Path | None
    arcgis_python: Path
    areas: str | None = None
    resolution: float = 5.0
    wayback_id: str = "58924"
    workers: int = 12
    max_tiles_per_chunk: int = 2000
    order: str = "largest-first"
    status_csv_name: str = "download_status.csv"
    redo: bool = False
    keep_parts: bool = False
    dry_run: bool = False
    refresh_estimates: bool = False


def log(message: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}")
    sys.stdout.flush()


def resolve_estimate_csv(options: DownloadOptions) -> Path:
    if options.boundary_source is None:
        if options.estimate_csv is None:
            raise RuntimeError("No estimate CSV configured and no boundary source available.")
        return options.estimate_csv

    target = default_generated_estimate_csv(options.work_dir, options.estimate_csv)
    if options.refresh_estimates or not target.exists():
        log(f"Generating estimate CSV from boundary source -> {target}")
        result = build_estimate_csv(
            options.arcgis_python,
            options.boundary_source,
            target,
            options.id_field,
            options.name_field,
            options.ascii_field,
            options.resolution,
        )
        log(
            "Boundary fields: id={0}; name={1}; ascii={2}; regions={3}".format(
                result.id_field,
                result.name_field or "-",
                result.ascii_field or "-",
                result.row_count,
            )
        )
    return target


def run_batch(options: DownloadOptions) -> dict[str, int]:
    options.out_dir.mkdir(parents=True, exist_ok=True)
    options.work_dir.mkdir(parents=True, exist_ok=True)
    ensure_web_mercator_prj(options.arcgis_python, options.work_dir, options.reference_dir)
    zoom = target_zoom(options.resolution)

    estimate_csv = resolve_estimate_csv(options)
    rows = load_estimates(estimate_csv, parse_areas(options.areas))
    if options.order == "largest-first":
        rows.sort(key=lambda row: int(row["tile_count"]), reverse=True)
    else:
        rows.sort(key=lambda row: int(row["id"]))
    if not rows:
        raise RuntimeError("No regions selected.")

    tile_cache_dir = default_tile_cache_dir(options.work_dir) / f"wayback_{options.wayback_id}" / f"z{zoom}"
    log(f"Estimate CSV: {estimate_csv}")
    log(f"Output directory: {options.out_dir}")
    log(f"Work directory: {options.work_dir}")
    log(f"Shared tile cache: {tile_cache_dir}")
    log("Selected regions: " + ",".join(str(row["id"]) for row in rows))
    log(f"Target resolution: {options.resolution} m/px -> Esri tile zoom {zoom}")
    log(f"Max tiles per internal chunk: {options.max_tiles_per_chunk}; workers: {options.workers}")

    planned = []
    total_parts = 0
    for row in rows:
        chunks = split_area(row, options.max_tiles_per_chunk)
        planned.append((row, chunks))
        total_parts += len(chunks)
        log(
            "Region {0:03d} {1}: {2} tiles -> {3} internal chunk(s)".format(
                int(row["id"]), row.get("county", ""), row["tile_count"], len(chunks)
            )
        )

    if options.dry_run:
        log(f"Dry run only. Planned internal chunks: {total_parts}")
        return {"completed": 0, "failed": 0, "planned": len(planned), "parts": total_parts}

    status_csv = options.out_dir / options.status_csv_name
    completed = 0
    failed = 0
    for row, chunks in planned:
        area_id = int(row["id"])
        output_stem = sanitize_output_stem(area_id, row.get("ascii"))
        manifest_row = dict(row)
        manifest_row["ascii"] = output_stem
        final_name = f"{output_stem}_5m_clipped.tif"
        final_tif = options.out_dir / final_name
        if final_tif.exists() and not options.redo:
            log(f"Region {area_id:03d}: already exists, skipped -> {final_tif}")
            write_manifest_row(status_csv, manifest_row, "skipped", final_tif, "already exists")
            completed += 1
            continue

        clipped_parts: list[Path] = []
        try:
            log(f"Region {area_id:03d} {row.get('county', '')}: start.")
            for index, chunk in enumerate(chunks, 1):
                cmin, cmax, rmin, rmax = chunk
                part_base = f"{output_stem}_part_{index:04d}"
                clipped_part = options.work_dir / f"{part_base}_clipped.tif"
                if clipped_part.exists() and not options.redo:
                    log(f"Region {area_id:03d} chunk {index}/{len(chunks)}: clipped part exists, reuse.")
                    clipped_parts.append(clipped_part)
                    continue

                raw_tif = build_mosaic_chunk(
                    wayback_id=options.wayback_id,
                    workers=options.workers,
                    work_dir=options.work_dir,
                    reference_dir=options.reference_dir,
                    zoom=zoom,
                    col_min=cmin,
                    col_max=cmax,
                    row_min=rmin,
                    row_max=rmax,
                    output_base=part_base,
                    cache_dir=tile_cache_dir,
                    log=log,
                )
                clip_feature = str(row.get("feature_class") or options.boundary_source or "")
                if not clip_feature:
                    raise RuntimeError("Missing feature_class in estimate CSV and no boundary source was configured.")
                clipped = clip_with_arcgis(
                    options.arcgis_python,
                    options.work_dir,
                    raw_tif,
                    part_base,
                    clip_feature,
                    str(row.get("clip_where", "") or ""),
                )
                clipped_parts.append(clipped)
                delete_raster_family(raw_tif)
                log(f"Region {area_id:03d} chunk {index}/{len(chunks)}: done.")

            if len(clipped_parts) == 1:
                copy_raster_family(clipped_parts[0], final_tif)
            else:
                log(f"Region {area_id:03d}: merging {len(clipped_parts)} internal chunk(s) into whole raster.")
                mosaic_to_whole(options.arcgis_python, clipped_parts, options.out_dir, final_name)

            if not options.keep_parts:
                for part in clipped_parts:
                    delete_raster_family(part)

            log(f"Region {area_id:03d}: finished -> {final_tif}")
            write_manifest_row(status_csv, manifest_row, "done", final_tif, "")
            completed += 1
        except Exception as exc:
            failed += 1
            message = repr(exc)
            log(f"Region {area_id:03d}: FAILED: {message}")
            write_manifest_row(status_csv, manifest_row, "failed", final_tif, message)

    log(f"Batch finished. Completed/skipped regions: {completed}; failed regions: {failed}")
    if failed:
        raise SystemExit(1)
    return {"completed": completed, "failed": failed, "planned": len(planned), "parts": total_parts}
