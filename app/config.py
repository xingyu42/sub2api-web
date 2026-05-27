from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUB2API_BASE_URL: str
    SUB2API_ADMIN_KEY: str
    LOGIN_PASSWORD: str
    SESSION_SECRET: str
    SUB2API_VERIFY_SSL: bool = True
    REQUEST_TIMEOUT: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
