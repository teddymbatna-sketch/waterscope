from waterscope.main import bienvenue


def test_bienvenue():
    assert bienvenue().startswith("WaterScope")
