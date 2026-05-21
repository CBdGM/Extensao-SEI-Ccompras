from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional
import secrets


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Integração Compras-SEI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(64)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str = ""  # Fernet key, 32 bytes base64-encoded

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://compras_sei:compras_sei_pass@db:5432/compras_sei"

    # CORS — comma-separated string to avoid pydantic-settings JSON parsing issues
    # Example: "http://localhost,http://localhost:5173"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:80,http://localhost"

    # File Upload
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 20

    # SEI Integration (can also be configured via admin panel)
    SEI_SOAP_URL: Optional[str] = None
    SEI_SIGLA_SISTEMA: Optional[str] = None
    SEI_IDENTIFICACAO_SERVICO: Optional[str] = None
    SEI_ID_UNIDADE_DEFAULT: Optional[str] = None
    SEI_ENABLE_WRITE_OPERATIONS: bool = False
    SEI_REQUEST_TIMEOUT: int = 30
    SEI_MAX_RETRIES: int = 3
    SEI_WRITE_TIMEOUT_SECONDS: int = 30
    # Default SEI IdSerie for external artifact documents (Tipo R)
    SEI_DEFAULT_EXTERNAL_DOCUMENT_SERIES_ID: str = ""
    # Default SEI IdSerie for the comprovation document
    SEI_DEFAULT_CONFIRMATION_DOCUMENT_SERIES_ID: str = ""
    # Default IdTipoConferencia (required by some SEI versions)
    SEI_DEFAULT_TIPO_CONFERENCIA_ID: str = ""

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 10

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        if not v:
            from cryptography.fernet import Fernet
            return Fernet.generate_key().decode()
        return v

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
