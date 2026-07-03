from __future__ import annotations

import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from PIL import Image


WAYBACK_SERVICE = (
    "https://wayback.maptiles.arcgis.com/arcgis/rest/services/"
    "World_Imagery/MapServer"
)
ORIGIN_SHIFT = 20037508.342789244
INITIAL_RESOLUTION = 156543.03392804097
TILE_SIZE = 256
SESSION_POOL_SIZE = 32

_thread_local = threading.local()


def target_zoom(resolution_m: float) -> int:
    if resolution_m <= 0:
        raise ValueError("resolution must be greater than zero")
    zoom = int(math.ceil(math.log(INITIAL_RESOLUTION / resolution_m, 2)))
    return max(0, min(23, zoom))


def lonlat_to_web_mercator(lon: float, lat: float) -> tuple[float, float]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    x = lon * ORIGIN_SHIFT / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) / (math.pi / 180.0)
    y = y * ORIGIN_SHIFT / 180.0
    return x, y


def web_mercator_to_lonlat(x: float, y: float) -> tuple[float, float]:
    lon = (x / ORIGIN_SHIFT) * 180.0
    lat = (y / ORIGIN_SHIFT) * 180.0
    lat = 180.0 / math.pi * (2.0 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
    return lon, lat


def tile_chunk_bbox(col_min: int, col_max: int, row_min: int, row_max: int, zoom: int) -> list[float]:
    res = INITIAL_RESOLUTION / (2**zoom)
    span = TILE_SIZE * res
    left = -ORIGIN_SHIFT + col_min * span
    right = -ORIGIN_SHIFT + (col_max + 1) * span
    top = ORIGIN_SHIFT - row_min * span
    bottom = ORIGIN_SHIFT - (row_max + 1) * span
    min_lon, min_lat = web_mercator_to_lonlat(left, bottom)
    max_lon, max_lat = web_mercator_to_lonlat(right, top)
    return [min_lon, min_lat, max_lon, max_lat]


def write_world_files(tif_path: Path, left: float, top: float, pixel_size: float, prj_source: Path) -> None:
    tfw_path = tif_path.with_suffix(".tfw")
    tfw_path.write_text(
        "\n".join(
            [
                f"{pixel_size:.12f}",
                "0.0",
                "0.0",
                f"{-pixel_size:.12f}",
                f"{left + pixel_size / 2.0:.12f}",
                f"{top - pixel_size / 2.0:.12f}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    tif_path.with_suffix(".prj").write_text(prj_source.read_text(), encoding="utf-8")


def create_http_session() -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=SESSION_POOL_SIZE,
        pool_maxsize=SESSION_POOL_SIZE,
        max_retries=0,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 Batch Downloader",
        }
    )
    return session


def get_thread_session() -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = create_http_session()
        _thread_local.session = session
    return session


def clear_thread_session(session: requests.Session | None = None) -> None:
    current = getattr(_thread_local, "session", None)
    if session is None or current is session:
        if current is not None:
            try:
                current.close()
            except Exception:
                pass
        if hasattr(_thread_local, "session"):
            delattr(_thread_local, "session")


def download_tile(
    session: requests.Session | None,
    wayback_id: str,
    zoom: int,
    row: int,
    col: int,
    cache_dir: Path,
    retries: int = 5,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    tile_path = cache_dir / f"{wayback_id}_z{zoom}_r{row}_c{col}.jpg"
    if tile_path.is_file() and tile_path.stat().st_size > 0:
        return tile_path

    url = f"{WAYBACK_SERVICE}/tile/{wayback_id}/{zoom}/{row}/{col}"
    last_error: Exception | None = None
    active_session = session
    for attempt in range(1, retries + 1):
        tmp_path = tile_path.with_name(f"{tile_path.name}.part.{os.getpid()}.{attempt}")
        response = None
        try:
            if active_session is None:
                active_session = get_thread_session()
            response = active_session.get(url, timeout=(10, 60))
            response.raise_for_status()
            if not response.headers.get("content-type", "").lower().startswith("image/"):
                raise RuntimeError(f"Tile request did not return an image: {url}")
            tmp_path.write_bytes(response.content)
            tmp_path.replace(tile_path)
            return tile_path
        except Exception as exc:
            last_error = exc
            if active_session is not None:
                if session is None:
                    clear_thread_session(active_session)
                else:
                    try:
                        active_session.close()
                    except Exception:
                        pass
                active_session = None
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass
            if attempt < retries:
                time.sleep(min(20, attempt * 2))
        finally:
            if response is not None:
                response.close()
    raise last_error  # type: ignore[misc]


def build_mosaic_chunk(
    *,
    wayback_id: str,
    workers: int,
    work_dir: Path,
    reference_dir: Path,
    zoom: int,
    col_min: int,
    col_max: int,
    row_min: int,
    row_max: int,
    output_base: str,
    cache_dir: Path,
    log,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cols = col_max - col_min + 1
    rows = row_max - row_min + 1
    tile_count = cols * rows
    width = cols * TILE_SIZE
    height = rows * TILE_SIZE
    pixel_size = INITIAL_RESOLUTION / (2**zoom)

    log(f"{output_base}: {tile_count} tiles -> {width} x {height}px")
    raw_dir = work_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_tif = raw_dir / f"{output_base}_raw.tif"

    left = -ORIGIN_SHIFT + col_min * TILE_SIZE * pixel_size
    top = ORIGIN_SHIFT - row_min * TILE_SIZE * pixel_size
    image = Image.new("RGB", (width, height))
    jobs = [(row, col) for row in range(row_min, row_max + 1) for col in range(col_min, col_max + 1)]

    completed = 0
    started = time.time()
    worker_count = max(1, int(workers))
    if worker_count == 1:
        for row, col in jobs:
            tile_path = download_tile(None, wayback_id, zoom, row, col, cache_dir)
            with Image.open(tile_path) as tile_handle:
                tile = tile_handle.convert("RGB")
            image.paste(tile, ((col - col_min) * TILE_SIZE, (row - row_min) * TILE_SIZE))
            completed += 1
            if completed == tile_count or completed % max(1, min(100, tile_count)) == 0:
                elapsed = max(0.1, time.time() - started)
                log(f"{output_base}: downloaded/mosaicked {completed}/{tile_count} ({completed / elapsed:.1f} tiles/sec)")
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(download_tile, None, wayback_id, zoom, row, col, cache_dir): (row, col)
                for row, col in jobs
            }
            for future in as_completed(futures):
                row, col = futures[future]
                tile_path = future.result()
                with Image.open(tile_path) as tile_handle:
                    tile = tile_handle.convert("RGB")
                image.paste(tile, ((col - col_min) * TILE_SIZE, (row - row_min) * TILE_SIZE))
                completed += 1
                if completed == tile_count or completed % max(1, min(100, tile_count)) == 0:
                    elapsed = max(0.1, time.time() - started)
                    log(f"{output_base}: downloaded/mosaicked {completed}/{tile_count} ({completed / elapsed:.1f} tiles/sec)")

    image.save(raw_tif, compression="tiff_lzw")
    prj_source = work_dir / "web_mercator_aux_sphere.prj"
    if not prj_source.exists():
        prj_source = reference_dir / "web_mercator_aux_sphere.prj"
    write_world_files(raw_tif, left, top, pixel_size, prj_source)
    return raw_tif
