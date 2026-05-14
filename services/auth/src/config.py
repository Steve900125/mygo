"""Application settings — auto-discover .env by walking up from cwd."""

from functools import lru_cache

from dotenv import find_dotenv
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Auth service settings."""

    model_config = SettingsConfigDict(
        env_file=find_dotenv(usecwd=True),  
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- Database -----
    AUTH_DB_USER: str
    AUTH_DB_PASSWORD: str
    AUTH_DB_HOST: str
    POSTGRES_PORT: int
    AUTH_DB_NAME: str

    # ----- App -----
    AUTH_PORT: int = 8001

    # ----- JWT -----
    SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://"
            f"{self.AUTH_DB_USER}:{self.AUTH_DB_PASSWORD}"
            f"@{self.AUTH_DB_HOST}:{self.POSTGRES_PORT}"
            f"/{self.AUTH_DB_NAME}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
