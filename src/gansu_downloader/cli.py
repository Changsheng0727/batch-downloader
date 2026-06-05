from __future__ import annotations

import argparse
import json
from pathlib import Path

from .arcgis import DEFAULT_ARCGIS_PYTHON
from .batch import DownloadOptions, run_batch


DEFAULT_ROOT = Path(r"E:\yanjiusheng")
DEFAULT_ESTIMATE = DEFAULT_ROOT / "gansu_arcgis_ready" / "gansu_5m_county_estimate.csv"
DEFAULT_OUT_DIR = DEFAULT_ROOT / "gansu_5m_whole_downloads"
DEFAULT_WORK_DIR = DEFAULT_ROOT / "gansu_5m_work"
DEFAULT_QINGHAI_REFERENCE_DIR = DEFAULT_ROOT / "qinghai1_5m_downloads"


def load_config(path: Path | None) -> dict[str, object]:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download Gansu county imagery and leave one whole GeoTIFF per county.")
    parser.add_argument("--config", type=Path, help="Optional JSON config path.")
    parser.add_argument("--estimate-csv", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--qinghai-reference-dir", type=Path)
    parser.add_argument("--arcgis-python", type=Path)
    parser.add_argument("--areas", help="County IDs to run, e.g. 1,3,71-72. Default: all.")
    parser.add_argument("--resolution", type=float)
    parser.add_argument("--wayback-id")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--max-tiles-per-chunk", type=int)
    parser.add_argument("--order", choices=["id", "largest-first"])
    parser.add_argument("--redo", action="store_true")
    parser.add_argument("--keep-parts", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    options = DownloadOptions(
        estimate_csv=args.estimate_csv or Path(config.get("estimate_csv", DEFAULT_ESTIMATE)),
        out_dir=args.out_dir or Path(config.get("out_dir", DEFAULT_OUT_DIR)),
        work_dir=args.work_dir or Path(config.get("work_dir", DEFAULT_WORK_DIR)),
        qinghai_reference_dir=args.qinghai_reference_dir or Path(config.get("qinghai_reference_dir", DEFAULT_QINGHAI_REFERENCE_DIR)),
        arcgis_python=args.arcgis_python or Path(config.get("arcgis_python", DEFAULT_ARCGIS_PYTHON)),
        areas=args.areas or config.get("areas"),
        resolution=args.resolution if args.resolution is not None else float(config.get("resolution", 5.0)),
        wayback_id=args.wayback_id or str(config.get("wayback_id", "58924")),
        workers=args.workers if args.workers is not None else int(config.get("workers", 8)),
        max_tiles_per_chunk=(
            args.max_tiles_per_chunk
            if args.max_tiles_per_chunk is not None
            else int(config.get("max_tiles_per_chunk", 2000))
        ),
        order=args.order or str(config.get("order", "largest-first")),
        redo=args.redo or bool(config.get("redo", False)),
        keep_parts=args.keep_parts or bool(config.get("keep_parts", False)),
        dry_run=args.dry_run or bool(config.get("dry_run", False)),
    )
    run_batch(options)


if __name__ == "__main__":
    main()
