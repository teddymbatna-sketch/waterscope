import calendar
from datetime import date, timedelta


def _filters(waterbody_id: str, start: date | None = None, end: date | None = None) -> list[dict]:
    filters = [{"term": {"waterbody_id": waterbody_id}}]
    date_range = {}
    if start:
        date_range["gte"] = start.isoformat()
    if end:
        date_range["lte"] = end.isoformat()
    if date_range:
        filters.append({"range": {"timestamp": date_range}})
    return filters


def shift_months(day: date, months: int) -> date:
    years, month_index = divmod(day.month - 1 + months, 12)
    year, month = day.year + years, month_index + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


# Question 1 - Serie temporelle de la surface d'un lac
def surface_area_query(waterbody_id: str, start: date | None = None, end: date | None = None) -> dict:
    return {
        "query": {"bool": {"filter": _filters(waterbody_id, start, end)}},
        "sort": [{"timestamp": "asc"}],
        "size": 1000,
        "source": ["timestamp", "surface_area_hectares", "clear_ratio"],
    }


def parse_surface_area(response: dict) -> list[dict]:
    return [
        {
            "date": hit["_source"]["timestamp"],
            "surface_area_hectares": hit["_source"]["surface_area_hectares"],
            "clear_ratio": hit["_source"].get("clear_ratio"),
        }
        for hit in response["hits"]["hits"]
    ]


# Question 5 - Moyennes mensuelles (sert aussi a la question 2)
def seasonal_query(waterbody_id: str) -> dict:
    return {
        "size": 0,
        "query": {"bool": {"filter": _filters(waterbody_id)}},
        "aggs": {
            "per_month": {
                "date_histogram": {
                    "field": "timestamp",
                    "calendar_interval": "month",
                    "format": "yyyy-MM",
                    "min_doc_count": 1,
                },
                "aggs": {"avg_area": {"avg": {"field": "surface_area_hectares"}}},
            }
        },
    }


def _monthly_averages(response: dict) -> list[tuple[int, int, float]]:
    return [
        (int(bucket["key_as_string"][:4]), int(bucket["key_as_string"][5:7]), bucket["avg_area"]["value"])
        for bucket in response["aggregations"]["per_month"]["buckets"]
    ]


def parse_seasonal(response: dict) -> list[dict]:
    by_month: dict[int, list[float]] = {}
    for _, month, value in _monthly_averages(response):
        by_month.setdefault(month, []).append(value)
    return [
        {
            "month": month,
            "average_hectares": round(sum(values) / len(values), 2),
            "years": len(values),
        }
        for month, values in sorted(by_month.items())
    ]


# Question 2 - Derniere mesure vs moyenne du meme mois les annees precedentes
def latest_query(waterbody_id: str) -> dict:
    return {
        "query": {"bool": {"filter": _filters(waterbody_id)}},
        "sort": [{"timestamp": "desc"}],
        "size": 1,
        "source": ["timestamp", "surface_area_hectares"],
    }


def compare_to_history(latest_response: dict, monthly_response: dict) -> dict | None:
    hits = latest_response["hits"]["hits"]
    if not hits:
        return None
    current = hits[0]["_source"]
    current_date = date.fromisoformat(current["timestamp"][:10])
    history = [
        value
        for year, month, value in _monthly_averages(monthly_response)
        if month == current_date.month and year < current_date.year
    ]
    average = round(sum(history) / len(history), 2) if history else None
    change = (
        round((current["surface_area_hectares"] - average) / average * 100, 1) if average else None
    )
    return {
        "date": current["timestamp"],
        "current_hectares": current["surface_area_hectares"],
        "historical_average_hectares": average,
        "years_in_history": len(history),
        "change_percent": change,
    }


# Question 3 / US3.2 - Secheresse : date_range + bucket_script dans Elasticsearch
def drought_query(end: date, months: int = 12, window: int = 3) -> dict:
    recent_from = shift_months(end, -window)
    past_to = shift_months(end, -months)
    past_from = shift_months(past_to, -window)
    return {
        "size": 0,
        "aggs": {
            "by_lake": {
                "terms": {"field": "waterbody_id", "size": 1000},
                "aggs": {
                    "periods": {
                        "date_range": {
                            "field": "timestamp",
                            "ranges": [
                                {"key": "past", "from": past_from.isoformat(), "to": past_to.isoformat()},
                                {
                                    "key": "recent",
                                    "from": recent_from.isoformat(),
                                    "to": (end + timedelta(days=1)).isoformat(),
                                },
                            ],
                        },
                        "aggs": {"avg_area": {"avg": {"field": "surface_area_hectares"}}},
                    },
                    "change_pct": {
                        "bucket_script": {
                            "buckets_path": {
                                "past": "periods['past']>avg_area",
                                "recent": "periods['recent']>avg_area",
                            },
                            "script": "(params.recent - params.past) / params.past * 100",
                        }
                    },
                },
            }
        },
    }


def parse_drought(response: dict, threshold: float) -> list[dict]:
    results = []
    for lake in response["aggregations"]["by_lake"]["buckets"]:
        change = lake.get("change_pct", {}).get("value")
        if change is None or change > -threshold:
            continue
        periods = {bucket["key"]: bucket["avg_area"]["value"] for bucket in lake["periods"]["buckets"]}
        results.append(
            {
                "waterbody_id": lake["key"],
                "past_average_hectares": round(periods["past"], 2),
                "recent_average_hectares": round(periods["recent"], 2),
                "change_percent": round(change, 1),
            }
        )
    return sorted(results, key=lambda result: result["change_percent"])


# Question 4 - Variation rapide entre deux mesures successives
def all_measures_query() -> dict:
    return {
        "size": 10000,
        "sort": [{"waterbody_id": "asc"}, {"timestamp": "asc"}],
        "source": ["waterbody_id", "timestamp", "surface_area_hectares"],
    }


def detect_rapid_changes(response: dict, threshold: float, days: int) -> list[dict]:
    alerts = []
    previous: dict[str, tuple[date, float]] = {}
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        lake = source["waterbody_id"]
        day = date.fromisoformat(source["timestamp"][:10])
        area = source["surface_area_hectares"]
        before = previous.get(lake)
        if before:
            gap = (day - before[0]).days
            if 0 < gap <= days and before[1] > 0:
                change = (area - before[1]) / before[1] * 100
                if abs(change) >= threshold:
                    alerts.append(
                        {
                            "waterbody_id": lake,
                            "from_date": before[0].isoformat(),
                            "to_date": day.isoformat(),
                            "days": gap,
                            "from_hectares": before[1],
                            "to_hectares": area,
                            "change_percent": round(change, 1),
                        }
                    )
        previous[lake] = (day, area)
    return alerts
