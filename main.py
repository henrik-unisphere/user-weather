from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api import weather
from app.auth import routes as auth_routes
from app.auth.middleware import JWTMiddleware
from app.auth.settings import settings
from app.dependencies import get_oauth_wrapper, get_user_repo

app = FastAPI(title="Weather + Keycloak Demo")
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)


app.add_middleware(JWTMiddleware, oauth_wrapper=get_oauth_wrapper(get_user_repo()))
app.include_router(auth_routes.router, tags=["auth"])
app.include_router(weather.router, tags=["weather"])


@app.get("/health")
def health_check():  # noqa: ANN201
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app")
