import sys

import requests

from waterscope import config

if not config.SENTINEL_CLIENT_ID or not config.SENTINEL_CLIENT_SECRET:
    print("ERREUR : SENTINEL_CLIENT_ID ou SENTINEL_CLIENT_SECRET manquant dans .env")
    sys.exit(1)

response = requests.post(
    config.TOKEN_URL,
    data={
        "grant_type": "client_credentials",
        "client_id": config.SENTINEL_CLIENT_ID,
        "client_secret": config.SENTINEL_CLIENT_SECRET,
    },
    timeout=30,
)

if response.ok:
    expires = response.json()["expires_in"]
    print(f"OK : jeton obtenu, valable {expires} secondes")
else:
    print(f"ECHEC ({response.status_code}) : {response.text}")
    sys.exit(1)
