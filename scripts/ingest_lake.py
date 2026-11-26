import argparse
import logging

from waterscope import es_client
from waterscope.ingestion import ingest_lake
from waterscope.lakes import LAKES
from waterscope.main import setup_logging

parser = argparse.ArgumentParser(description="Ingestion Sentinel Hub -> Elasticsearch")
parser.add_argument("--lake", required=True, choices=[*LAKES, "all"], help="identifiant du lac, ou all")
parser.add_argument("--months", type=int, default=24, help="nombre de mois a remonter")
args = parser.parse_args()

setup_logging()
es = es_client.get_client()

if es_client.create_index(es):
    logging.info("Index '%s' cree", es_client.INDEX_NAME)

lakes = list(LAKES.values()) if args.lake == "all" else [LAKES[args.lake]]
for lake in lakes:
    logging.info("=== %s ===", lake["name"])
    total = ingest_lake(es, lake, months=args.months)
    logging.info("%s : %d mesures enregistrees", lake["name"], total)

es.indices.refresh(index=es_client.INDEX_NAME)
