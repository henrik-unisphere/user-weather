from pydantic import BaseModel


class WeatherResponse(BaseModel):
    city: str
    temperature: float
    temp_min: float
    temp_max: float
    description: str
    humidity: int
    wind_speed: float


class ForecastItem(BaseModel):
    date: str
    temperature: float
    description: str
