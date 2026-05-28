from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SUB2API_BASE_URL: str
    SUB2API_ADMIN_KEY: str
    LOGIN_PASSWORD: str
    SESSION_SECRET: str
    SUB2API_VERIFY_SSL: bool = True
    REQUEST_TIMEOUT: int = 30
    
    # 安全配置
    COOKIE_SECURE: bool = True  # 生产环境必须为 true，本地 HTTP 开发可设为 false
    SUB2API_CA_BUNDLE: Optional[str] = None  # 自签证书路径（可选）
    DEBUG: bool = False  # 生产环境必须为 False，开发环境可设为 True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
