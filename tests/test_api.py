from datetime import date

import pytest
from fastapi.testclient import TestClient

from waterscope import analytics
from waterscope.api import app, get_es


class FakeES:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


@pytest.fixture
def client_with():
    def make(*responses):
        fake = FakeES(*responses)
        app.dependency_overrides[get_es] = lambda: fake
        return TestClient(app), fake

    yield make
    app.dependency_overrides.clear()


def hit(timestamp, area, lake="lac_du_der"):
    return {
        "_source": {
            "waterbody_id": lake,
            "timestamp": timestamp,
            "surface_area_hectares": area,
            "clear_ratio": 0.99,
        }
    }


def monthly(*buckets):
    return {
        "aggregations": {
            "per_month": {
                "buckets": [{"key_as_string": month, "avg_area": {"value": area}} for month, area in buckets]
            }
        }
    }


def lake_bucket(lake, past, recent, change):
    bucket = {
        "key": lake,
        "periods": {
            "buckets": [
                {"key": "past", "avg_area": {"value": past}},
                {"key": "recent", "avg_area": {"value": recent}},
            ]
        },
    }
    if change is not None:
        bucket["change_pct"] = {"value": change}
    return bucket


# Question 1
def test_surface_area_returns_measures(client_with):
    client, fake = client_with({"hits": {"hits": [hit("2025-03-10", 4200.0), hit("2025-04-02", 4100.0)]}})

    response = client.get("/api/waterbodies/lac_du_der/surface-area")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["measures"][0] == {"date": "2025-03-10", "surface_area_hectares": 4200.0, "clear_ratio": 0.99}
    assert fake.calls[0]["query"]["bool"]["filter"][0] == {"term": {"waterbody_id": "lac_du_der"}}


def test_surface_area_unknown_lake_returns_404(client_with):
    client, _ = client_with({"hits": {"hits": []}})

    assert client.get("/api/waterbodies/lac_inconnu/surface-area").status_code == 404


def test_surface_area_query_with_dates():
    query = analytics.surface_area_query("lac_du_der", date(2025, 1, 1), date(2025, 12, 31))
    assert query["query"]["bool"]["filter"][1] == {
        "range": {"timestamp": {"gte": "2025-01-01", "lte": "2025-12-31"}}
    }


# Question 2
def test_current_vs_average_compares_same_month_of_previous_years(client_with):
    client, _ = client_with(
        {"hits": {"hits": [hit("2026-03-10", 4200.0)]}},
        monthly(("2025-03", 4000.0), ("2025-11", 2700.0), ("2026-03", 4200.0)),
    )

    body = client.get("/api/waterbodies/lac_du_der/current-vs-average").json()

    assert body["current_hectares"] == 4200.0
    assert body["historical_average_hectares"] == 4000.0
    assert body["years_in_history"] == 1
    assert body["change_percent"] == 5.0


# Question 3
def test_shift_months_handles_year_and_month_ends():
    assert analytics.shift_months(date(2026, 3, 31), -1) == date(2026, 2, 28)
    assert analytics.shift_months(date(2026, 1, 15), -2) == date(2025, 11, 15)


def test_drought_risk_keeps_only_lakes_below_threshold(client_with):
    client, fake = client_with(
        {
            "aggregations": {
                "by_lake": {
                    "buckets": [
                        lake_bucket("lac_a", 4000.0, 2000.0, -50.0),
                        lake_bucket("lac_b", 4000.0, 3600.0, -10.0),
                        lake_bucket("lac_c", None, 3000.0, None),
                    ]
                }
            }
        }
    )

    body = client.get("/api/analytics/drought-risk?end=2026-11-25").json()

    assert body["count"] == 1
    assert body["waterbodies"][0] == {
        "waterbody_id": "lac_a",
        "past_average_hectares": 4000.0,
        "recent_average_hectares": 2000.0,
        "change_percent": -50.0,
    }
    ranges = fake.calls[0]["aggs"]["by_lake"]["aggs"]["periods"]["date_range"]["ranges"]
    assert ranges[0] == {"key": "past", "from": "2025-08-25", "to": "2025-11-25"}


def test_drought_risk_rejects_window_longer_than_period(client_with):
    client, _ = client_with()

    assert client.get("/api/analytics/drought-risk?months=3&window=3").status_code == 400


# Question 4
def test_rapid_changes_flags_big_change_within_period(client_with):
    client, _ = client_with(
        {
            "hits": {
                "hits": [
                    hit("2025-01-01", 4000.0),
                    hit("2025-01-20", 2800.0),
                    hit("2025-03-01", 2900.0),
                ]
            }
        }
    )

    body = client.get("/api/analytics/rapid-changes?threshold=25&days=30").json()

    assert body["count"] == 1
    assert body["alerts"][0]["change_percent"] == -30.0
    assert body["alerts"][0]["days"] == 19


# Question 5
def test_seasonal_pattern_averages_same_month_across_years(client_with):
    client, _ = client_with(monthly(("2025-03", 4000.0), ("2025-11", 2700.0), ("2026-03", 4200.0)))

    response = client.get("/api/waterbodies/lac_du_der/seasonal-pattern")

    assert response.status_code == 200
    assert response.json()["months"] == [
        {"month": 3, "average_hectares": 4100.0, "years": 2},
        {"month": 11, "average_hectares": 2700.0, "years": 1},
    ]
