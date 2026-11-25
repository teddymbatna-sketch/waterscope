from elasticsearch import Elasticsearch, NotFoundError

from waterscope import config

INDEX_NAME = "waterbody_stats"

INDEX_MAPPING = {
    "properties": {
        "waterbody_id": {"type": "keyword"},
        "name": {"type": "text"},
        "timestamp": {"type": "date"},
        "surface_area_hectares": {"type": "float"},
        "geometry": {"type": "geo_shape"},
    }
}


def get_client() -> Elasticsearch:
    return Elasticsearch(f"http://{config.ES_HOST}:{config.ES_PORT}")


# T1.2.1 - Sante du cluster
def check_health(es: Elasticsearch) -> str:
    return es.cluster.health()["status"]


# T1.2.2 - Creation de l'index
def create_index(es: Elasticsearch, index: str = INDEX_NAME) -> bool:
    if es.indices.exists(index=index):
        return False
    es.indices.create(index=index, mappings=INDEX_MAPPING)
    return True


# T1.2.3 - CRUD
def make_doc_id(waterbody_id: str, timestamp: str) -> str:
    return f"{waterbody_id}_{timestamp}"


def create_stat(es: Elasticsearch, doc: dict, index: str = INDEX_NAME) -> str:
    doc_id = make_doc_id(doc["waterbody_id"], doc["timestamp"])
    es.index(index=index, id=doc_id, document=doc, refresh="wait_for")
    return doc_id


def get_stat(es: Elasticsearch, doc_id: str, index: str = INDEX_NAME) -> dict | None:
    try:
        return es.get(index=index, id=doc_id)["_source"]
    except NotFoundError:
        return None


def update_stat(es: Elasticsearch, doc_id: str, fields: dict, index: str = INDEX_NAME) -> None:
    es.update(index=index, id=doc_id, doc=fields, refresh="wait_for")


def delete_stat(es: Elasticsearch, doc_id: str, index: str = INDEX_NAME) -> None:
    es.delete(index=index, id=doc_id, refresh="wait_for")
