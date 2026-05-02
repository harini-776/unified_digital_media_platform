from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


_WEAK_JWT_SECRETS = {
    "change-me-in-production",
    "changeme",
    "secret",
    "password",
    "default",
    "test",
    "dev",
}


class Settings(BaseSettings):
    # App
    app_name: str = "TrustMedia API"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database — required, no defaults (boot fails loudly if missing)
    database_url: str
    database_url_async: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Auth — jwt_secret is required and validated
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60

    # Storage
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"
    max_upload_size_mb: int = 500

    # IPFS / Pinata
    pinata_api_key: str = ""
    pinata_secret_key: str = ""
    pinata_jwt: str = ""

    # Blockchain
    rpc_url: str = "https://rpc-amoy.polygon.technology"
    contract_address: str = ""
    private_key: str = ""

    # AI
    model_device: str = "cpu"
    model_batch_size: int = 16
    demo_mode: bool = True

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, v: str) -> str:
        if v.lower().strip() in _WEAK_JWT_SECRETS:
            raise ValueError(
                "JWT_SECRET is set to a known weak/default value. "
                "Generate a strong secret with: "
                "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        if len(v) < 32:
            raise ValueError(
                f"JWT_SECRET must be at least 32 characters (got {len(v)}). "
                "Generate a strong secret with: "
                "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
