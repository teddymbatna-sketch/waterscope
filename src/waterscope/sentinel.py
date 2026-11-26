import logging
import math
import time

import requests

from waterscope import config

logger = logging.getLogger(__name__)

STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
PIXEL_SIZE_M = 10
MIN_CLEAR_RATIO = 0.95

# NDWI = (B03 - B08) / (B03 + B08) ; eau si ndwi > 0
# SCL 4 vegetation, 5 sol nu, 6 eau, 7 non classe = pixels sans nuage
EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B03", "B08", "SCL", "dataMask"] }],
    output: [
      { id: "water", bands: 1, sampleType: "UINT8" },
      { id: "dataMask", bands: 1 }
    ]
  };
}

function evaluatePixel(s) {
  const clear = [4, 5, 6, 7].includes(s.SCL);
  const ndwi = (s.B03 - s.B08) / (s.B03 + s.B08);
  return {
    water: [ndwi > 0 ? 1 : 0],
    dataMask: [s.dataMask === 1 && clear ? 1 : 0]
  };
}
"""

_token_cache = {"value": None, "expires_at": 0.0}


# T2.1.2 - Jeton OAuth2 mis en cache, renouvele 60 s avant expiration
def get_token() -> str:
    if _token_cache["value"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["value"]
    response = requests.post(
        config.TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": config.SENTINEL_CLIENT_ID,
            "client_secret": config.SENTINEL_CLIENT_SECRET,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    _token_cache["value"] = payload["access_token"]
    _token_cache["expires_at"] = time.time() + payload["expires_in"]
    logger.info("Nouveau jeton Copernicus obtenu")
    return _token_cache["value"]


# Pixels d'environ 10 m x 10 m, exprimes en degres (la geometrie est en lon/lat)
def resolution_degrees(geometry: dict) -> tuple[float, float]:
    ring = geometry["coordinates"][0]
    lat = sum(point[1] for point in ring) / len(ring)
    resy = PIXEL_SIZE_M / 111_320
    resx = resy / math.cos(math.radians(lat))
    return resx, resy


# T2.2.1 - Requete Statistical API (date_to exclue)
def build_payload(geometry: dict, date_from: str, date_to: str) -> dict:
    resx, resy = resolution_degrees(geometry)
    return {
        "input": {
            "bounds": {
                "geometry": geometry,
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {"maxCloudCoverage": config.MAX_CLOUD_COVERAGE},
                }
            ],
        },
        "aggregation": {
            "timeRange": {"from": f"{date_from}T00:00:00Z", "to": f"{date_to}T00:00:00Z"},
            "aggregationInterval": {"of": "P1D"},
            "evalscript": EVALSCRIPT,
            "resx": resx,
            "resy": resy,
        },
    }


# T2.2.2 - Nombre de pixels d'eau -> hectares
def parse_statistics(result: dict) -> list[dict]:
    measures = []
    for item in result.get("data", []):
        date = item["interval"]["from"][:10]
        if "error" in item:
            logger.warning("%s : erreur %s", date, item["error"])
            continue
        stats = item["outputs"]["water"]["bands"]["B0"]["stats"]
        total = stats["sampleCount"]
        clear = total - stats["noDataCount"]
        if clear == 0:
            logger.info("%s : aucun pixel exploitable", date)
            continue
        clear_ratio = clear / total
        if clear_ratio < MIN_CLEAR_RATIO:
            logger.info("%s : ignore, %.0f%% de pixels sans nuage", date, clear_ratio * 100)
            continue
        water_pixels = stats["mean"] * clear
        area_ha = water_pixels * PIXEL_SIZE_M**2 / 10_000
        measures.append(
            {
                "date": date,
                "surface_area_hectares": round(area_ha, 2),
                "clear_ratio": round(clear_ratio, 3),
            }
        )
    return measures


def fetch_water_stats(geometry: dict, date_from: str, date_to: str) -> list[dict]:
    payload = build_payload(geometry, date_from, date_to)
    headers = {"Authorization": f"Bearer {get_token()}"}
    response = requests.post(STATS_URL, json=payload, headers=headers, timeout=120)
    if not response.ok:
        # T2.2.3 - Journaliser les erreurs
        logger.error("Statistical API : %s %s", response.status_code, response.text)
        response.raise_for_status()
    return parse_statistics(response.json())
