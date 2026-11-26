import logging
from datetime import date

import requests

from waterscope import es_client
from waterscope.sentinel import fetch_water_stats

logger = logging.getLogger(__name__)


# T2.3.1 - Decoupage en mois : [(debut, fin_exclue), ...] du plus ancien au plus recent
def month_ranges(end: date, months: int) -> list[tuple[str, str]]:
    ranges = []
    year, month = end.year, end.month
    for _ in range(months):
        prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
        ranges.append((date(prev_year, prev_month, 1).isoformat(), date(year, month, 1).isoformat()))
        year, month = prev_year, prev_month
    return list(reversed(ranges))


# T2.3.2 + T2.3.3 - Un appel Sentinel Hub par mois, chaque mesure enregistree dans ES
def ingest_lake(es, lake: dict, months: int = 24, end: date | None = None) -> int:
    end = end or date.today().replace(day=1)
    stored = 0
    for date_from, date_to in month_ranges(end, months):
        try:
            measures = fetch_water_stats(lake["geometry"], date_from, date_to)
        except requests.RequestException as error:
            logger.error("%s : echec, mois ignore (%s)", date_from[:7], error)
            continue
        for m in measures:
            doc = {
                "waterbody_id": lake["waterbody_id"],
                "name": lake["name"],
                "timestamp": m["date"],
                "surface_area_hectares": m["surface_area_hectares"],
                "clear_ratio": m["clear_ratio"],
                "geometry": lake["geometry"],
            }
            es_client.create_stat(es, doc, refresh=False)
            stored += 1
        logger.info("%s : %d mesure(s) enregistree(s)", date_from[:7], len(measures))
    return stored
