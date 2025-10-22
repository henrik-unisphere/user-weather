from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
from app.api.weather import router as weather_router
from app.api.user import router as user_router

load_dotenv()


app = FastAPI()
app.include_router(weather_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
