from __future__ import annotations

import csv
import math
from pathlib import Path


def parse_areas(text: str | None) -> set[int] | None:
    if not text:
        return None
    selected: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = [int(value.strip()) for value in part.split("-", 1)]
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))
    return selected


def load_estimates(path: Path, selected: set[int] | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            area_id = int(row["id"])
            if selected and area_id not in selected:
                continue
            for key in ["col_min", "col_max", "row_min", "row_max", "tile_count", "pixel_width", "pixel_height"]:
                row[key] = int(row[key])
            for key in ["xmin", "ymin", "xmax", "ymax", "approx_uncompressed_rgb_gb"]:
                row[key] = float(row[key])
            row["id"] = area_id
            rows.append(row)
    return rows


def split_area(row: dict[str, object], max_tiles: int) -> list[tuple[int, int, int, int]]:
    col_min = int(row["col_min"])
    col_max = int(row["col_max"])
    row_min = int(row["row_min"])
    row_max = int(row["row_max"])
    cols = col_max - col_min + 1
    rows = row_max - row_min + 1

    if cols * rows <= max_tiles:
        return [(col_min, col_max, row_min, row_max)]

    ratio = float(cols) / max(1.0, float(rows))
    chunk_cols = max(1, int(math.floor(math.sqrt(max_tiles * ratio))))
    chunk_cols = min(cols, chunk_cols)
    chunk_rows = max(1, int(math.floor(float(max_tiles) / chunk_cols)))
    chunk_rows = min(rows, chunk_rows)

    chunks: list[tuple[int, int, int, int]] = []
    row_start = row_min
    while row_start <= row_max:
        row_stop = min(row_max, row_start + chunk_rows - 1)
        col_start = col_min
        while col_start <= col_max:
            col_stop = min(col_max, col_start + chunk_cols - 1)
            chunks.append((col_start, col_stop, row_start, row_stop))
            col_start = col_stop + 1
        row_start = row_stop + 1
    return chunks
