from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .arcgis import clip_with_arcgis, ensure_web_mercator_prj, mosaic_to_whole
from .estimates import load_estimates, parse_areas, split_area
from .files import cleanup_dir, copy_raster_family, delete_raster_family
from .status import write_manifest_row
from .tiles import build_mosaic_chunk, target_zoom, tile_chunk_bbox


@dataclass
class DownloadOptions:
    estimate_csv: Path
    out_dir: Path
    work_dir: Path
    reference_dir: Path
    arcgis_python: Path
    areas: str | None = None
    resolution: float = 5.0
    wayback_id: str = "58924"
    workers: int = 8
    max_tiles_per_chunk: int = 2000
    order: str = "largest-first"
    status_csv_name: str = "download_status.csv"
    redo: bool = False
    keep_parts: bool = False
    dry_run: bool = False


def log(message: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}")
    sys.stdout.flush()


def run_batch(options: DownloadOptions) -> dict[str, int]:
    options.out_dir.mkdir(parents=True, exist_ok=True)
    options.work_dir.mkdir(parents=True, exist_ok=True)
    ensure_web_mercator_prj(options.arcgis_python, options.work_dir, options.reference_dir)

    rows = load_estimates(options.estimate_csv, parse_areas(options.areas))
    if options.order == "largest-first":
        rows.sort(key=lambda row: int(row["tile_count"]), reverse=True)
    else:
        rows.sort(key=lambda row: int(row["id"]))
    if not rows:
        raise RuntimeError("No regions selected.")

    log(f"Output directory: {options.out_dir}")
    log(f"Work directory: {options.work_dir}")
    log("Selected regions: " + ",".join(str(row["id"]) for row in rows))
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
        final_name = f"{row['ascii']}_5m_clipped.tif"
        final_tif = options.out_dir / final_name
        if final_tif.exists() and not options.redo:
            log(f"Region {int(row['id']):03d}: already exists, skipped -> {final_tif}")
            write_manifest_row(status_csv, row, "skipped", final_tif, "already exists")
            completed += 1
            continue

        county_work = options.work_dir / str(row["ascii"])
        clipped_parts: list[Path] = []
        try:
            log(f"Region {int(row['id']):03d} {row.get('county', '')}: start.")
            for index, chunk in enumerate(chunks, 1):
                cmin, cmax, rmin, rmax = chunk
                part_base = f"{row['ascii']}_part_{index:04d}"
                clipped_part = options.work_dir / f"{part_base}_clipped.tif"
                if clipped_part.exists() and not options.redo:
                    log(f"Region {int(row['id']):03d} chunk {index}/{len(chunks)}: clipped part exists, reuse.")
                    clipped_parts.append(clipped_part)
                    continue

                bbox = tile_chunk_bbox(cmin, cmax, rmin, rmax, target_zoom(options.resolution))
                cache_dir = county_work / "tile_cache" / f"part_{index:04d}"
                raw_tif = build_mosaic_chunk(
                    wayback_id=options.wayback_id,
                    resolution=options.resolution,
                    workers=options.workers,
                    work_dir=options.work_dir,
                    reference_dir=options.reference_dir,
                    bbox=bbox,
                    col_min=cmin,
                    col_max=cmax,
                    row_min=rmin,
                    row_max=rmax,
                    output_base=part_base,
                    cache_dir=cache_dir,
                    log=log,
                )
                clipped = clip_with_arcgis(
                    options.arcgis_python,
                    options.work_dir,
                    raw_tif,
                    part_base,
                    str(row["feature_class"]),
                )
                clipped_parts.append(clipped)
                delete_raster_family(raw_tif)
                cleanup_dir(cache_dir)
                log(f"Region {int(row['id']):03d} chunk {index}/{len(chunks)}: done.")

            if len(clipped_parts) == 1:
                copy_raster_family(clipped_parts[0], final_tif)
            else:
                log(f"Region {int(row['id']):03d}: merging {len(clipped_parts)} internal chunk(s) into whole raster.")
                mosaic_to_whole(options.arcgis_python, clipped_parts, options.out_dir, final_name)

            if not options.keep_parts:
                for part in clipped_parts:
                    delete_raster_family(part)
                cleanup_dir(county_work)

            log(f"Region {int(row['id']):03d}: finished -> {final_tif}")
            write_manifest_row(status_csv, row, "done", final_tif, "")
            completed += 1
        except Exception as exc:
            failed += 1
            message = repr(exc)
            log(f"Region {int(row['id']):03d}: FAILED: {message}")
            write_manifest_row(status_csv, row, "failed", final_tif, message)

    log(f"Batch finished. Completed/skipped regions: {completed}; failed regions: {failed}")
    if failed:
        raise SystemExit(1)
    return {"completed": completed, "failed": failed, "planned": len(planned), "parts": total_parts}
