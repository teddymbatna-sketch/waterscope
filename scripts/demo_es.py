from waterscope import es_client

es = es_client.get_client()

print("1. Sante du cluster :", es_client.check_health(es))

if es_client.create_index(es):
    print("2. Index 'waterbody_stats' cree")
else:
    print("2. Index 'waterbody_stats' existe deja")

doc = {
    "waterbody_id": "lac_test_001",
    "name": "Lac de test",
    "timestamp": "2024-06-01",
    "surface_area_hectares": 120.5,
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[2.0, 48.0], [2.1, 48.0], [2.1, 48.1], [2.0, 48.1], [2.0, 48.0]]],
    },
}

doc_id = es_client.create_stat(es, doc)
print("3. CREATE :", doc_id)

print("4. READ   :", es_client.get_stat(es, doc_id)["surface_area_hectares"], "ha")

es_client.update_stat(es, doc_id, {"surface_area_hectares": 118.0})
print("5. UPDATE :", es_client.get_stat(es, doc_id)["surface_area_hectares"], "ha")

es_client.delete_stat(es, doc_id)
print("6. DELETE :", es_client.get_stat(es, doc_id))
