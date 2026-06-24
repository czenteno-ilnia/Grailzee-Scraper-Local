import requests
import base64
import time

CLIENT_ID = "JuanMuoz-WatchesA-PRD-6e0ba47ae-77c52d7a"
CLIENT_SECRET = "PRD-e0ba47ae4859-2bf2-4243-9dfe-a210"

_TOKEN = None
_TOKEN_EXP = 0

def get_access_token():
    global _TOKEN, _TOKEN_EXP

    if _TOKEN and time.time() < _TOKEN_EXP:
        return _TOKEN

    auth = base64.b64encode(
        f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope"
    }

    r = requests.post(
        "https://api.ebay.com/identity/v1/oauth2/token",
        headers=headers,
        data=data
    )

    r.raise_for_status()
    j = r.json()

    _TOKEN = j["access_token"]
    _TOKEN_EXP = time.time() + j["expires_in"] - 60

    return _TOKEN
