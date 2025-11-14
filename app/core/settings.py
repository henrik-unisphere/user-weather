from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENWEATHER_API_KEY: str
    DATABASE_URL: str

    SESSION_SECRET: str  # von dir generiert
    APP_BASE_URL: str = "http://localhost:8000"

    ZITADEL_ISSUER: str
    ZITADEL_CLIENT_ID: str
    ZITADEL_CLIENT_SECRET: str
    ZITADEL_REDIRECT_URI: str
    ZITADEL_POST_LOGOUT_REDIRECT_URI: str
    ZITADEL_SCOPES: str

    # Admin machine client for managing users/roles
    ZITADEL_ADMIN_CLIENT_ID: str
    ZITADEL_ADMIN_CLIENT_SECRET: str
    ZITADEL_PROJECT_ID: str  # Your project ID in Zitadel

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
