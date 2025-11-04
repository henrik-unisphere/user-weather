from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    OPENWEATHER_API_KEY: str
    DATABASE_URL: str

    KEYCLOAK_CLIENT_ID: str
    KEYCLOAK_CLIENT_SECRET: str
    KEYCLOAK_ISSUER: str  # z.B. http://localhost:8080/realms/master

    SESSION_SECRET: str  # von dir generiert
    APP_BASE_URL: str = "http://localhost:8000"

    KEYCLOAK_REALM: str
    KEYCLOAK_ADMIN_CLIENT_ID: str
    KEYCLOAK_ADMIN_CLIENT_SECRET: str
    KEYCLOAK_BASE: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
