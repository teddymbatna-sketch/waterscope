from waterscope import sentinel


def make_item(date, mean, total, masked):
    return {
        "interval": {"from": f"{date}T00:00:00Z", "to": f"{date}T23:59:59Z"},
        "outputs": {
            "water": {
                "bands": {
                    "B0": {"stats": {"mean": mean, "sampleCount": total, "noDataCount": masked}}
                }
            }
        },
    }


def test_parse_statistics_converts_pixels_to_hectares():
    result = {"data": [make_item("2024-06-05", 0.25, 1000, 20)]}
    measures = sentinel.parse_statistics(result)
    # 0.25 x 980 pixels sans nuage = 245 pixels d'eau x 0.01 ha
    assert measures == [
        {"date": "2024-06-05", "surface_area_hectares": 2.45, "clear_ratio": 0.98}
    ]


def test_parse_statistics_skips_cloudy_dates():
    # 84 % sans nuage : sous le seuil de 95 %
    result = {"data": [make_item("2024-06-23", 0.3, 1000, 160)]}
    assert sentinel.parse_statistics(result) == []


def test_resolution_is_about_10_meters():
    geometry = {"type": "Polygon", "coordinates": [[[4.6, 48.5], [4.9, 48.5], [4.9, 48.7], [4.6, 48.5]]]}
    resx, resy = sentinel.resolution_degrees(geometry)
    assert abs(resy * 111_320 - 10) < 0.01
    assert resx > resy
