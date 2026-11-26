def _rectangle(west: float, south: float, east: float, north: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    }


LAKES = {
    "lac_du_der": {
        "waterbody_id": "lac_du_der",
        "name": "Lac du Der-Chantecoq",
        "geometry": _rectangle(4.64, 48.52, 4.88, 48.65),
    },
    "lac_d_orient": {
        "waterbody_id": "lac_d_orient",
        "name": "Lac d'Orient",
        "geometry": _rectangle(4.29, 48.22, 4.43, 48.33),
    },
    "lac_de_serre_poncon": {
        "waterbody_id": "lac_de_serre_poncon",
        "name": "Lac de Serre-Poncon",
        "geometry": _rectangle(6.24, 44.40, 6.50, 44.58),
    },
}

LAC_DU_DER = LAKES["lac_du_der"]
