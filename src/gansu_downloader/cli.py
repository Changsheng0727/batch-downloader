from __future__ import annotations

import argparse
import json
from pathlib import Path

from .batch import DownloadOptions, run_batch
from .settings import default_work_dir, detect_arcgis_python


def load_config(path: Path | None) -> dict[str, object]:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def path_setting(parser: argparse.ArgumentParser, args_value: Path | None, config: dict[str, object], key: str) -> Path:
    value = args_value or config.get(key)
    if not value:
        parser.error(f"Missing required path: --{key.replace('_', '-')} or config field '{key}'")
    return Path(value)


def optional_path_setting(args_value: Path | None, config: dict[str, object], *keys: str) -> Path | None:
    if args_value is not None:
        return args_value
    for key in keys:
        value = config.get(key)
        if value:
            return Path(value)
    return None


def string_setting(args_value: str | None, config: dict[str, object], key: str, default: str | None = None) -> str | None:
    if args_value is not None:
        return args_value
    value = config.get(key)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def reference_dir_setting(parser: argparse.ArgumentParser, args: argparse.Namespace, config: dict[str, object]) -> Path | None:
    value = (
        args.reference_dir
        or args.qinghai_reference_dir
        or config.get("reference_dir")
        or config.get("qinghai_reference_dir")
    )
    return Path(value) if value else None


def arcgis_python_setting(parser: argparse.ArgumentParser, args: argparse.Namespace, config: dict[str, object]) -> Path:
    explicit = optional_path_setting(args.arcgis_python, config, "arcgis_python")
    detected = detect_arcgis_python(explicit)
    if detected is None:
        parser.error("Could not find ArcGIS Python. Provide --arcgis-python or config field 'arcgis_python'.")
    return detected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download regional imagery and leave one whole GeoTIFF per region.")
    parser.add_argument("--config", type=Path, help="Optional JSON config path.")
    parser.add_argument("--estimate-csv", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--boundary-source", type=Path, help="Polygon feature class / shapefile used for auto-generating estimate CSV.")
    parser.add_argument("--id-field", help="Unique numeric ID field in the boundary source. Auto-detected when omitted.")
    parser.add_argument("--name-field", help="Display name field in the boundary source. Auto-detected when omitted.")
    parser.add_argument("--ascii-field", help="Field used for output filename stems. Auto-detected when omitted.")
    parser.add_argument("--reference-dir", type=Path)
    parser.add_argument("--qinghai-reference-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--arcgis-python", type=Path)
    parser.add_argument("--areas", help="Region IDs to run, e.g. 1,3,71-72. Default: all.")
    parser.add_argument("--resolution", type=float)
    parser.add_argument("--wayback-id")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--max-tiles-per-chunk", type=int)
    parser.add_argument("--order", choices=["id", "largest-first"])
    parser.add_argument("--status-csv-name")
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--keep-parts", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh-estimates", action="store_true", help="Rebuild the estimate CSV from the boundary source before running.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    estimate_csv = optional_path_setting(args.estimate_csv, config, "estimate_csv")
    out_dir = path_setting(parser, args.out_dir, config, "out_dir")
    work_dir = default_work_dir(out_dir, optional_path_setting(args.work_dir, config, "work_dir"))
    boundary_source = optional_path_setting(args.boundary_source, config, "boundary_source")
    if estimate_csv is None and boundary_source is None:
        parser.error("Provide --estimate-csv or --boundary-source so the downloader knows what to process.")
    options = DownloadOptions(
        estimate_csv=estimate_csv,
        out_dir=out_dir,
        work_dir=work_dir,
        boundary_source=boundary_source,
        id_field=string_setting(args.id_field, config, "id_field"),
        name_field=string_setting(args.name_field, config, "name_field"),
        ascii_field=string_setting(args.ascii_field, config, "ascii_field"),
        reference_dir=reference_dir_setting(parser, args, config),
        arcgis_python=arcgis_python_setting(parser, args, config),
        areas=args.areas or str(config.get("areas", "") or ""),
        resolution=args.resolution if args.resolution is not None else float(config.get("resolution", 5.0)),
        wayback_id=args.wayback_id or str(config.get("wayback_id", "58924")),
        workers=args.workers if args.workers is not None else int(config.get("workers", 12)),
        max_tiles_per_chunk=(
            args.max_tiles_per_chunk
            if args.max_tiles_per_chunk is not None
            else int(config.get("max_tiles_per_chunk", 2000))
        ),
        order=args.order or str(config.get("order", "largest-first")),
        status_csv_name=args.status_csv_name or str(config.get("status_csv_name", "download_status.csv")),
        redo=args.redo or bool(config.get("redo", False)),
        keep_parts=args.keep_parts or bool(config.get("keep_parts", False)),
        dry_run=args.dry_run or bool(config.get("dry_run", False)),
        refresh_estimates=args.refresh_estimates or bool(config.get("refresh_estimates", False)),
    )
    run_batch(options)


if __name__ == "__main__":
    main()
