from datetime import date

from waterscope import ingestion

LAKE = {"waterbody_id": "lac_test", "name": "Lac de test", "geometry": {"type": "Polygon"}}


def test_month_ranges():
    assert ingestion.month_ranges(date(2026, 1, 1), 3) == [
        ("2025-10-01", "2025-11-01"),
        ("2025-11-01", "2025-12-01"),
        ("2025-12-01", "2026-01-01"),
    ]


def test_ingest_lake_stores_each_measure(monkeypatch):
    stored = []
    monkeypatch.setattr(
        ingestion,
        "fetch_water_stats",
        lambda geometry, date_from, date_to: [
            {"date": date_from, "surface_area_hectares": 100.0, "clear_ratio": 0.99}
        ],
    )
    monkeypatch.setattr(
        ingestion.es_client, "create_stat", lambda es, doc, **kwargs: stored.append(doc)
    )

    count = ingestion.ingest_lake(None, LAKE, months=3, end=date(2026, 1, 1))

    assert count == 3
    assert stored[0]["waterbody_id"] == "lac_test"
    assert stored[0]["timestamp"] == "2025-10-01"
    assert stored[0]["surface_area_hectares"] == 100.0
