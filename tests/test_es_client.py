import pytest

from waterscope import es_client

TEST_INDEX = "waterbody_stats_test"


@pytest.fixture
def es():
    client = es_client.get_client()
    if not client.ping():
        pytest.skip("Elasticsearch non disponible")
    client.indices.delete(index=TEST_INDEX, ignore_unavailable=True)
    es_client.create_index(client, TEST_INDEX)
    yield client
    client.indices.delete(index=TEST_INDEX, ignore_unavailable=True)


def test_health(es):
    assert es_client.check_health(es) in ("green", "yellow")


def test_crud(es):
    doc = {
        "waterbody_id": "lac_test",
        "name": "Lac de test",
        "timestamp": "2024-06-01",
        "surface_area_hectares": 120.5,
    }
    doc_id = es_client.create_stat(es, doc, TEST_INDEX)
    assert es_client.get_stat(es, doc_id, TEST_INDEX)["surface_area_hectares"] == 120.5

    es_client.update_stat(es, doc_id, {"surface_area_hectares": 118.0}, TEST_INDEX)
    assert es_client.get_stat(es, doc_id, TEST_INDEX)["surface_area_hectares"] == 118.0

    es_client.delete_stat(es, doc_id, TEST_INDEX)
    assert es_client.get_stat(es, doc_id, TEST_INDEX) is None
