from pathlib import Path

from gansu_downloader.files import copy_raster_family, delete_raster_family, move_raster_family


def write_raster_family(base: Path, stem: str, payload: bytes) -> Path:
    tif = base / f"{stem}.tif"
    tif.write_bytes(payload)
    tif.with_suffix(".tfw").write_text("tfw", encoding="utf-8")
    tif.with_suffix(".prj").write_text("prj", encoding="utf-8")
    Path(str(tif) + ".aux.xml").write_text("aux", encoding="utf-8")
    Path(str(tif) + ".xml").write_text("xml", encoding="utf-8")
    return tif


def assert_raster_family_exists(tif: Path) -> None:
    assert tif.exists()
    assert tif.with_suffix(".tfw").exists()
    assert tif.with_suffix(".prj").exists()
    assert Path(str(tif) + ".aux.xml").exists()
    assert Path(str(tif) + ".xml").exists()


def test_copy_raster_family_replaces_existing_destination(tmp_path: Path) -> None:
    src = write_raster_family(tmp_path, "source", b"new")
    dest = write_raster_family(tmp_path, "dest", b"old")

    copy_raster_family(src, dest)

    assert_raster_family_exists(dest)
    assert dest.read_bytes() == b"new"


def test_move_raster_family_moves_sidecars_and_replaces_destination(tmp_path: Path) -> None:
    src = write_raster_family(tmp_path, "move_source", b"moved")
    dest = write_raster_family(tmp_path, "move_dest", b"old")

    move_raster_family(src, dest)

    assert_raster_family_exists(dest)
    assert dest.read_bytes() == b"moved"
    assert not src.exists()
    assert not src.with_suffix(".tfw").exists()


def test_delete_raster_family_removes_known_sidecars(tmp_path: Path) -> None:
    tif = write_raster_family(tmp_path, "delete_me", b"bye")

    delete_raster_family(tif)

    assert not tif.exists()
    assert not tif.with_suffix(".tfw").exists()
    assert not tif.with_suffix(".prj").exists()
    assert not Path(str(tif) + ".aux.xml").exists()
    assert not Path(str(tif) + ".xml").exists()
