from gansu_downloader.estimates import parse_areas, split_area
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
