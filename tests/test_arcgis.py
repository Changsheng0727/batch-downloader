import csv
import json
from pathlib import Path

from gansu_downloader import arcgis


def test_build_estimate_csv_writes_rows_from_arcgis_output(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "meta": {
            "id_field": "OBJECTID",
            "name_field": "county",
            "ascii_field": "ascii",
            "row_count": 1,
        },
        "rows": [
            {
                "id": 48,
                "county": "Minqin",
                "ascii": "Minqin",
                "feature_class": r"D:\data\counties.shp",
                "clip_where": '"OBJECTID" = 48',
                "col_min": 1,
                "col_max": 2,
                "row_min": 3,
                "row_max": 4,
                "tile_count": 4,
                "pixel_width": 512,
                "pixel_height": 512,
                "xmin": 100.0,
                "ymin": 35.0,
                "xmax": 101.0,
                "ymax": 36.0,
                "approx_uncompressed_rgb_gb": 0.0007,
            }
        ],
    }

    def fake_run_temp_arcgis_script(*args, **kwargs) -> str:
        return "ArcPy info line\n" + json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr(arcgis, "_run_temp_arcgis_script", fake_run_temp_arcgis_script)

    estimate_csv = tmp_path / "generated.csv"
    result = arcgis.build_estimate_csv(
        arcgis_python=Path(r"C:\ArcGIS\python.exe"),
        boundary_source=Path(r"D:\data\counties.shp"),
        estimate_csv=estimate_csv,
        id_field=None,
        name_field=None,
        ascii_field=None,
        resolution=5.0,
    )

    assert result.path == estimate_csv
    assert result.id_field == "OBJECTID"
    assert result.name_field == "county"
    assert result.ascii_field == "ascii"
    assert result.row_count == 1

    with estimate_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        written = list(csv.DictReader(handle))

    assert len(written) == 1
    assert written[0]["id"] == "48"
    assert written[0]["ascii"] == "Minqin"
    assert written[0]["clip_where"] == '"OBJECTID" = 48'
