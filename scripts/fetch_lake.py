import logging

from waterscope.lakes import LAC_DU_DER
from waterscope.main import setup_logging
from waterscope.sentinel import fetch_water_stats

setup_logging()

lake = LAC_DU_DER
measures = fetch_water_stats(lake["geometry"], "2024-04-01", "2024-07-01")

logging.info("%s : %d mesures exploitables en juin 2024", lake["name"], len(measures))
for m in measures:
    logging.info(
        "%s  %10.2f ha  (%.0f%% sans nuage)",
        m["date"],
        m["surface_area_hectares"],
        m["clear_ratio"] * 100,
    )
