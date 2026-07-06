from pathlib import Path

from gansu_downloader.estimates import parse_areas, sanitize_output_stem, split_area
from gansu_downloader.settings import default_generated_estimate_csv, default_tile_cache_dir, default_work_dir
from gansu_downloader.tiles import target_zoom


def test_parse_areas_supports_ranges():
    assert parse_areas("1,3,5-7") == {1, 3, 5, 6, 7}


def test_split_area_keeps_small_area_single_chunk():
    row = {"col_min": 1, "col_max": 3, "row_min": 10, "row_max": 12}
    assert split_area(row, 100) == [(1, 3, 10, 12)]


def test_split_area_splits_large_area():
    row = {"col_min": 1, "col_max": 20, "row_min": 1, "row_max": 20}
    chunks = split_area(row, 50)
    assert len(chunks) > 1
    assert chunks[0][0] == 1
    assert chunks[0][2] == 1


def test_target_zoom_for_five_meter_resolution():
    assert target_zoom(5.0) == 15


def test_sanitize_output_stem_normalizes_ascii_text():
    assert sanitize_output_stem(7, "Min Qin County") == "Min_Qin_County"


def test_sanitize_output_stem_falls_back_for_non_ascii_text():
    assert sanitize_output_stem(48, "\u6c11\u52e4\u53bf") == "region_048"


def test_default_work_dir_and_generated_estimate_path():
    out_dir = Path("E:/imagery/out")
    work_dir = default_work_dir(out_dir, None)
    assert work_dir == out_dir / "_work"
    assert default_generated_estimate_csv(work_dir, None) == work_dir / "region_estimate.generated.csv"
    assert default_tile_cache_dir(work_dir) == work_dir / "tile_cache"
