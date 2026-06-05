from __future__ import annotations

import csv
import time
from pathlib import Path


def write_manifest_row(path: Path, row: dict[str, object], status: str, final_tif: Path, message: str) -> None:
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        if not exists:
            writer.writerow(["time", "id", "county", "ascii", "tile_count", "status", "final_tif", "message"])
        writer.writerow(
            [
                time.strftime("%Y-%m-%d %H:%M:%S"),
                row["id"],
                row.get("county", ""),
                row["ascii"],
                row["tile_count"],
                status,
                str(final_tif),
                message,
            ]
        )
