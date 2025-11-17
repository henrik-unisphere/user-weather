from fastapi import APIRouter, Depends, HTTPException, Query
import requests
from typing import List
from app.auth.auth_dep import require_authenticated_user, require_role_premium
from app.schemas.weather_model import WeatherResponse, ForecastItem
from app.core.settings import settings

API_KEY = settings.OPENWEATHER_API_KEY
BASE_URL = "https://api.openweathermap.org/data/2.5"


router = APIRouter()
# dependencies=[Depends(require_authenticated_user)]


@router.get(
    "/weather_current",
    response_model=WeatherResponse,
    summary="Get Current Weather",
    description="Get Current Weather in City",
    tags=["weather"],
    responses={
        200: {
            "description": "Erfolg",
            "content": {
                "application/json": {
                    "example": {
                        "city": "London",
                        "temperature": 15.2,
                        "temp_min": 13.0,
                        "temp_max": 17.0,
                        "description": "clear sky",
                        "humidity": 70,
                        "wind_speed": 3.5,
                    }
                }
            },
        },
        401: {
            "description": "API-Key ungültig oder nicht autorisiert",
            "content": {"application/json": {"example": {"detail": "API-Key ungültig oder nicht autorisiert"}}},
        },
        404: {
            "description": "Stadt nicht gefunden",
            "content": {"application/json": {"example": {"detail": "Stadt nicht gefunden: <city>"}}},
        },
        502: {
            "description": "Upstream-Fehler (Timeout/Connection/unerwartetes Schema)",
            "content": {
                "application/json": {
                    "examples": {
                        "timeout": {
                            "summary": "Timeout/Connection",
                            "value": {"detail": "OpenWeather nicht erreichbar (Timeout/Connection)"},
                        },
                        "schema": {
                            "summary": "Antwortschema unerwartet",
                            "value": {"detail": "Unerwartetes Antwortschema von OpenWeather"},
                        },
                        "generic": {
                            "summary": "Sonstiger Fehler",
                            "value": {"detail": "Fehler beim Abrufen der Wetterdaten"},
                        },
                    }
                }
            },
        },
        422: {
            "description": "Validierungsfehler (z. B. leerer Query-Parameter)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "city"],
                                "msg": "Field required",
                                "type": "missing",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def get_weather(
    city: str = Query(..., min_length=1, description="Stadtname, z. B. 'Konstanz'"),
) -> WeatherResponse:
    city = city.strip()
    if not city:
        raise HTTPException(status_code=422, detail="city darf nicht leer sein")
    if not API_KEY:
        raise HTTPException(status_code=500, detail="OPENWEATHER_API_KEY fehlt")

    params = {"q": city, "appid": API_KEY, "units": "metric", "lang": "de"}

    try:
        response = requests.get(BASE_URL + "/weather", params=params, timeout=10)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        raise HTTPException(status_code=502, detail="OpenWeather nicht erreichbar (Timeout/Connection)")
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="Fehler beim Verbinden zu OpenWeather")

    # url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=de"
    # response = requests.get(url)

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="API-Key ungültig oder nicht autorisiert")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Stadt nicht gefunden: {city}")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Fehler beim Abrufen der Wetterdaten")

    try:
        data = response.json()
        result = WeatherResponse(
            city=data["name"],
            temperature=data["main"]["temp"],
            temp_min=data["main"]["temp_min"],
            temp_max=data["main"]["temp_max"],
            description=data["weather"][0]["description"],
            humidity=data["main"]["humidity"],
            wind_speed=data["wind"]["speed"],
        )
    except (ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail="Unerwartetes Antwortschema von OpenWeather")

    return result


@router.get(
    "/forecast",
    response_model=List[ForecastItem],
    summary="Get Weather Forecast in City",
    tags=["weather"],
    dependencies=[Depends(require_role_premium)],
    responses={
        200: {
            "description": "Erfolg",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "date": "2025-10-11",
                            "temperature": 15.2,
                            "description": "clear sky",
                        },
                        {
                            "date": "2025-10-12",
                            "temperature": 14.0,
                            "description": "cloudy",
                        },
                    ]
                }
            },
        },
        401: {
            "description": "API-Key ungültig oder nicht autorisiert",
            "content": {"application/json": {"example": {"detail": "API-Key ungültig oder nicht autorisiert"}}},
        },
        404: {
            "description": "Stadt nicht gefunden",
            "content": {"application/json": {"example": {"detail": "Stadt nicht gefunden: <city>"}}},
        },
        502: {
            "description": "Upstream-Fehler (Timeout/Connection/unerwartetes Schema)",
            "content": {
                "application/json": {
                    "examples": {
                        "timeout": {
                            "summary": "Timeout/Connection",
                            "value": {"detail": "OpenWeather nicht erreichbar (Timeout/Connection)"},
                        },
                        "schema": {
                            "summary": "Antwortschema unerwartet",
                            "value": {"detail": "Unerwartetes Antwortschema von OpenWeather"},
                        },
                        "generic": {
                            "summary": "Sonstiger Fehler",
                            "value": {"detail": "Fehler beim Abrufen der Wetterdaten"},
                        },
                    }
                }
            },
        },
        422: {
            "description": "Validierungsfehler (z. B. fehlender oder leerer city-Parameter / ungültige days)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["query", "city"],
                                "msg": "Field required",
                                "type": "value_error.missing",
                            }
                        ]
                    }
                }
            },
        },
    },
)
def get_forecast(city: str = Query(..., min_length=1, description="city name")) -> list[ForecastItem]:
    city = city.strip()
    if not city:
        raise HTTPException(status_code=422, detail="city darf nicht leer sein")
    if not API_KEY:
        raise HTTPException(status_code=500, detail="OPENWEATHER_API_KEY fehlt")

    params = {"q": city, "appid": API_KEY, "units": "metric", "lang": "de"}

    try:
        response = requests.get(BASE_URL + "/forecast", params=params, timeout=10)
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        raise HTTPException(status_code=502, detail="OpenWeather nicht erreichbar (Timeout/Connection)")
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=502, detail="Fehler beim Verbinden zu OpenWeather")

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="API-Key ungültig oder nicht autorisiert")
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Stadt nicht gefunden: {city}")
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Fehler beim Abrufen der Wetterdaten")

    try:
        data = response.json()

        items: List[ForecastItem] = []

        for slot in data["list"]:
            slot_time = slot.get("dt_txt")
            if not slot_time:
                continue
            if not slot_time.endswith("12:00:00"):
                continue

            date_str = slot_time.split(" ")[0]

            items.append(
                ForecastItem(
                    date=date_str,
                    temperature=slot["main"]["temp"],
                    description=slot["weather"][0]["description"],
                )
            )

            if len(items) == 3:
                break

        # result = ForecastItem(date=data["list"][0]["dt_txt"],
        #                       temperature=data["list"][0]["main"]["temp"],
        #                       description=data["list"][0]["weather"][0]["description"])

    except (ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail="Unerwartetes Antwortschema von OpenWeather")

    return items
