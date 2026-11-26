from waterscope.lakes import LAKES


def test_each_lake_has_matching_id_and_closed_rectangle():
    for lake_id, lake in LAKES.items():
        assert lake["waterbody_id"] == lake_id
        ring = lake["geometry"]["coordinates"][0]
        assert ring[0] == ring[-1]
        west, south = ring[0]
        east, north = ring[2]
        assert -180 <= west < east <= 180
        assert -90 <= south < north <= 90
