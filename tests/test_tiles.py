from pathlib import Path

from gansu_downloader.tiles import download_tile, tile_cache_path


class ExplodingSession:
    def get(self, *args, **kwargs):  # pragma: no cover - should never be reached
        raise AssertionError("Network request should not happen when a cached tile exists.")


def test_tile_cache_path_shards_by_row(tmp_path: Path) -> None:
    assert tile_cache_path(tmp_path, "58924", 15, 123, 456) == tmp_path / "r00123" / "58924_z15_r123_c456.jpg"


def test_download_tile_reuses_sharded_cache_without_network(tmp_path: Path) -> None:
    tile_path = tile_cache_path(tmp_path, "58924", 15, 123, 456)
    tile_path.parent.mkdir(parents=True, exist_ok=True)
    tile_path.write_bytes(b"cached")

    result = download_tile(ExplodingSession(), "58924", 15, 123, 456, tmp_path)

    assert result == tile_path


def test_download_tile_reuses_legacy_flat_cache_without_network(tmp_path: Path) -> None:
    legacy_tile_path = tmp_path / "58924_z15_r123_c456.jpg"
    legacy_tile_path.write_bytes(b"cached")

    result = download_tile(ExplodingSession(), "58924", 15, 123, 456, tmp_path)

    assert result == legacy_tile_path
