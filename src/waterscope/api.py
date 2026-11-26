from datetime import date

from elasticsearch import Elasticsearch
from fastapi import Depends, FastAPI, HTTPException, Query

from waterscope import analytics, es_client

app = FastAPI(
    title="WaterScope API",
    description="Suivi de la surface des plans d'eau a partir des donnees Sentinel-2",
    version="0.2.0",
)


def get_es() -> Elasticsearch:
    return es_client.get_client()


@app.get("/health")
def health(es: Elasticsearch = Depends(get_es)) -> dict:
    return {"elasticsearch": es_client.check_health(es)}


# US3.1 / Question 1 - Serie temporelle
@app.get("/api/waterbodies/{waterbody_id}/surface-area")
def surface_area(
    waterbody_id: str,
    start: date | None = None,
    end: date | None = None,
    es: Elasticsearch = Depends(get_es),
) -> dict:
    query = analytics.surface_area_query(waterbody_id, start, end)
    measures = analytics.parse_surface_area(es.search(index=es_client.INDEX_NAME, **query))
    if not measures:
        raise HTTPException(status_code=404, detail=f"Aucune mesure pour '{waterbody_id}' sur cette periode")
    return {"waterbody_id": waterbody_id, "count": len(measures), "measures": measures}


# Question 2 - Derniere mesure vs moyenne historique du meme mois
@app.get("/api/waterbodies/{waterbody_id}/current-vs-average")
def current_vs_average(waterbody_id: str, es: Elasticsearch = Depends(get_es)) -> dict:
    latest = es.search(index=es_client.INDEX_NAME, **analytics.latest_query(waterbody_id))
    monthly = es.search(index=es_client.INDEX_NAME, **analytics.seasonal_query(waterbody_id))
    result = analytics.compare_to_history(latest, monthly)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Aucune mesure pour '{waterbody_id}'")
    return {"waterbody_id": waterbody_id, **result}


# Question 5 - Cycle saisonnier
@app.get("/api/waterbodies/{waterbody_id}/seasonal-pattern")
def seasonal_pattern(waterbody_id: str, es: Elasticsearch = Depends(get_es)) -> dict:
    query = analytics.seasonal_query(waterbody_id)
    months = analytics.parse_seasonal(es.search(index=es_client.INDEX_NAME, **query))
    if not months:
        raise HTTPException(status_code=404, detail=f"Aucune mesure pour '{waterbody_id}'")
    return {"waterbody_id": waterbody_id, "months": months}


# US3.2 / Question 3 - Risque de secheresse
@app.get("/api/analytics/drought-risk")
def drought_risk(
    threshold: float = Query(40, gt=0, le=100, description="Baisse minimale en %"),
    months: int = Query(12, ge=2, description="Ecart entre les deux periodes comparees"),
    window: int = Query(3, ge=1, description="Duree de chaque periode, en mois"),
    end: date | None = None,
    es: Elasticsearch = Depends(get_es),
) -> dict:
    if window >= months:
        raise HTTPException(status_code=400, detail="window doit etre plus petit que months")
    end = end or date.today()
    query = analytics.drought_query(end, months, window)
    lakes = analytics.parse_drought(es.search(index=es_client.INDEX_NAME, **query), threshold)
    return {
        "threshold_percent": threshold,
        "months": months,
        "window_months": window,
        "end": end.isoformat(),
        "count": len(lakes),
        "waterbodies": lakes,
    }


# Question 4 - Alerte de variation rapide
@app.get("/api/analytics/rapid-changes")
def rapid_changes(
    threshold: float = Query(25, gt=0, description="Variation minimale en %"),
    days: int = Query(30, ge=1, description="Ecart maximal entre deux mesures, en jours"),
    es: Elasticsearch = Depends(get_es),
) -> dict:
    response = es.search(index=es_client.INDEX_NAME, **analytics.all_measures_query())
    alerts = analytics.detect_rapid_changes(response, threshold, days)
    return {"threshold_percent": threshold, "days": days, "count": len(alerts), "alerts": alerts}
