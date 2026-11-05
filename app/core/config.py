# Core application settings
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "RenewOps"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://renewops:renewops@localhost:5432/renewops"

    # CORS
    ALLOWED_ORIGINS: Union[str, List[str]] = ["*"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Security & API Protection
    MCP_SERVER_PORT: int = 8001
    MCP_API_KEY: str = ""  # If set, Claude/clients must send Bearer <MCP_API_KEY> or X-API-Key
    ADMIN_API_KEY: str = ""  # If set, REST write operations require Authorization or X-Admin-Key

    # Demo organization & default currency
    DEMO_ORG_ID: str = "00000000-0000-0000-0000-000000000001"
    DEMO_ORG_NAME: str = "Demo Organization"
    DEFAULT_CURRENCY: str = "INR"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
