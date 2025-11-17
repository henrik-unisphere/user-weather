import requests

KEYCLOAK_TOKEN_URL = "http://localhost:8080/oauth/v2/token"
CLIENT_ID = "m2m"
CLIENT_SECRET = "DH7e6WH2X1SxnenUjf4r1F2o3CvcXCzJAc4hawYg46h40jXgLMqX62nANrvaE0jN"


def get_token():
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "openid profile",
    }

    resp = requests.post(KEYCLOAK_TOKEN_URL, data=data)
    resp.raise_for_status()
    token = resp.json()["access_token"]
    return token


def call_weather_api(token):
    url = "http://127.0.0.1:8000/weather_current?city=Konstanz"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers)
    print("Status:", r.status_code)
    print("Response:", r.text)


if __name__ == "__main__":
    token = get_token()
    print("✅ Token geholt!")
    call_weather_api(token)
