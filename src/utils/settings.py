from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .env_utils import EnvUtils


class Settings(BaseSettings):
    host: str = Field(alias="HOST", default="0.0.0.0")
    port: int = Field(alias="PORT", default=8080, ge=1, le=65535)
    workers: int = Field(alias="WORKERS", default=1, ge=1)

    database_url: str = Field(alias="DATABASE_URL")
    database_schema: str = Field(alias="DATABASE_SCHEMA", default="public")
    database_url_for_agent: str = Field(alias="DATABASE_URL_FOR_AGENT", default="")

    cors_allowed_origins: str = Field(alias="CORS_ALLOWED_ORIGINS", default="*")

    mcp_server_url: str = Field(alias="MCP_SERVER_URL")
    mcp_server_name: str = Field(alias="MCP_SERVER_NAME", default="Repo MCP Server")
    mcp_prompt_name: str = Field(alias="MCP_PROMPT_NAME", default="code_intelligence_assistant")
    mcp_timeout: int = Field(alias="MCP_TIMEOUT", default=30, ge=1)

    openai_api_key: str = Field(alias="OPENAI_API_KEY", default="TEMP_OPENAI_API_KEY")
    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY", default="TEMP_ANTHROPIC_API_KEY")
    google_api_key: str = Field(alias="GOOGLE_API_KEY", default="TEMP_GOOGLE_API_KEY")

    hugging_face_embedding_model_id: str = Field(alias="HUGGING_FACE_EMBEDDING_MODEL_ID", default="sentence-transformers/all-MiniLM-L6-v2")

    default_agent_model: str = Field(alias="DEFAULT_AGENT_MODEL", default="openai:gpt-5.1")
    agent_model_temperature: float = Field(alias="AGENT_MODEL_TEMPERATURE", default=0.2, ge=0.0, le=1.0)

    summarization_trigger_threshold: float = Field(
        alias="SUMMARIZATION_TRIGGER_THRESHOLD",
        default=0.80,
        ge=0.1,
        le=0.95
    )

    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError('DATABASE_URL cannot be empty')
        if not v.startswith(('postgresql://', 'postgresql+psycopg://', 'postgresql+asyncpg://')):
            raise ValueError('DATABASE_URL must be a valid PostgreSQL connection string')
        return v

    @field_validator('mcp_server_url')
    @classmethod
    def validate_mcp_url(cls, v: str) -> str:
        if not v:
            raise ValueError('MCP_SERVER_URL cannot be empty')
        if not v.startswith(('http://', 'https://')):
            raise ValueError('MCP_SERVER_URL must be a valid HTTP(S) URL')
        return v

    model_config = SettingsConfigDict(
        env_file=EnvUtils.get_env_file_path(),
        extra="allow"
    )


# Global settings instance
settings = Settings()
