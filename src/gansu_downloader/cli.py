from __future__ import annotations

import argparse
import json
from pathlib import Path

from .batch import DownloadOptions, run_batch


def load_config(path: Path | None) -> dict[str, object]:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def path_setting(parser: argparse.ArgumentParser, args_value: Path | None, config: dict[str, object], key: str) -> Path:
    value = args_value or config.get(key)
    if not value:
        parser.error(f"Missing required path: --{key.replace('_', '-')} or config field '{key}'")
    return Path(value)


def reference_dir_setting(parser: argparse.ArgumentParser, args: argparse.Namespace, config: dict[str, object]) -> Path:
    value = (
        args.reference_dir
        or args.qinghai_reference_dir
        or config.get("reference_dir")
        or config.get("qinghai_reference_dir")
    )
    if not value:
        parser.error("Missing required path: --reference-dir or config field 'reference_dir'")
    return Path(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download regional imagery and leave one whole GeoTIFF per region.")
    parser.add_argument("--config", type=Path, help="Optional JSON config path.")
    parser.add_argument("--estimate-csv", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--work-dir", type=Path)
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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)
    options = DownloadOptions(
        estimate_csv=path_setting(parser, args.estimate_csv, config, "estimate_csv"),
        out_dir=path_setting(parser, args.out_dir, config, "out_dir"),
        work_dir=path_setting(parser, args.work_dir, config, "work_dir"),
        reference_dir=reference_dir_setting(parser, args, config),
        arcgis_python=path_setting(parser, args.arcgis_python, config, "arcgis_python"),
        areas=args.areas or str(config.get("areas", "") or ""),
        resolution=args.resolution if args.resolution is not None else float(config.get("resolution", 5.0)),
        wayback_id=args.wayback_id or str(config.get("wayback_id", "58924")),
        workers=args.workers if args.workers is not None else int(config.get("workers", 8)),
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
    )
    run_batch(options)


if __name__ == "__main__":
    main()
