"""
Application settings and configuration management.
"""

import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field
from enum import Enum


class LogLevel(str, Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    app_name: str = Field(default="Codebase RAG", description="Application name")
    app_env: str = Field(default="development", description="Application environment")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    
    # API settings
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8080, description="API port")
    api_workers: int = Field(default=4, description="Number of API workers")
    
    # ChromaDB settings
    chroma_host: str = Field(default="localhost", description="ChromaDB host")
    chroma_port: int = Field(default=8000, description="ChromaDB port")
    chroma_collection_name: str = Field(default="codebase_chunks", description="ChromaDB collection name")
    chroma_persist_directory: str = Field(default="./data/chroma", description="ChromaDB persist directory")
    
    # Neo4j settings
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j URI")
    neo4j_username: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(default="codebase-rag-2024", description="Neo4j password")
    neo4j_database: str = Field(default="neo4j", description="Neo4j database name")
    
    # Redis settings
    redis_url: str = Field(default="redis://localhost:6379", description="Redis URL")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    
    # PostgreSQL settings
    postgres_url: str = Field(default="postgresql://user:password@localhost:5432/codebase_rag", description="PostgreSQL URL")
    
    # MinIO settings
    minio_endpoint: str = Field(default="localhost:9000", description="MinIO endpoint")
    minio_access_key: str = Field(default="minioadmin", description="MinIO access key")
    minio_secret_key: str = Field(default="minioadmin", description="MinIO secret key")
    minio_secure: bool = Field(default=False, description="MinIO secure connection")
    
    # Embedding settings
    embedding_model: str = Field(default="microsoft/codebert-base", description="Embedding model")
    embedding_dimension: int = Field(default=768, description="Embedding dimension")
    embedding_device: str = Field(default="cpu", description="Embedding device")
    
    # Processing settings
    max_concurrent_repos: int = Field(default=10, description="Maximum concurrent repositories")
    max_workers: int = Field(default=4, description="Maximum worker processes")
    batch_size: int = Field(default=100, description="Batch size for processing")
    timeout_seconds: int = Field(default=300, description="Processing timeout")
    
    # Chunking settings
    max_chunk_size: int = Field(default=1000, description="Maximum chunk size")
    min_chunk_size: int = Field(default=100, description="Minimum chunk size")
    overlap_size: int = Field(default=200, description="Chunk overlap size")
    
    # Maven settings
    maven_enabled: bool = Field(default=True, description="Enable Maven processing")
    maven_resolution_strategy: str = Field(default="nearest", description="Maven resolution strategy")
    maven_include_test_dependencies: bool = Field(default=False, description="Include test dependencies")
    
    # Security settings
    auth_enabled: bool = Field(default=False, description="Enable authentication")
    jwt_secret_key: str = Field(default="change-this-secret-key", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_hours: int = Field(default=24, description="JWT expiration hours")
    
    # Monitoring settings
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=9090, description="Prometheus port")
    jaeger_enabled: bool = Field(default=False, description="Enable Jaeger tracing")
    jaeger_endpoint: str = Field(default="http://localhost:14268/api/traces", description="Jaeger endpoint")
    
    # File processing settings
    max_file_size: int = Field(default=1024 * 1024, description="Maximum file size in bytes")
    supported_extensions: List[str] = Field(
        default=[".py", ".java", ".js", ".ts", ".go", ".rs", ".cpp", ".c", ".h", ".hpp"],
        description="Supported file extensions"
    )
    exclude_patterns: List[str] = Field(
        default=["**/node_modules/**", "**/target/**", "**/.git/**", "**/build/**", "**/__pycache__/**"],
        description="File patterns to exclude"
    )
    
    # Repository settings
    workspace_dir: str = Field(default="./data/repositories", description="Repository workspace directory")
    git_timeout: int = Field(default=300, description="Git operation timeout")
    
    # Cache settings
    cache_ttl: int = Field(default=300, description="Cache TTL in seconds")
    cache_size: int = Field(default=1000, description="Cache size")
    
    # Performance settings
    query_timeout: int = Field(default=30, description="Query timeout in seconds")
    connection_pool_size: int = Field(default=10, description="Connection pool size")

    # --- New: Bedrock / LLM configuration ---
    bedrock_model_id: Optional[str] = Field(default=None, description="AWS Bedrock model id", alias="BEDROCK_MODEL_ID")
    aws_region: Optional[str] = Field(default=None, description="AWS region for Bedrock", alias="AWS_REGION")
    aws_profile: Optional[str] = Field(default=None, description="AWS profile name", alias="AWS_PROFILE")
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key id", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS secret access key", alias="AWS_SECRET_ACCESS_KEY")
    llm_max_input_tokens: int = Field(default=8000, description="Max input tokens for LLM", alias="LLM_MAX_INPUT_TOKENS")
    llm_max_output_tokens: int = Field(default=1024, description="Max output tokens for LLM", alias="LLM_MAX_OUTPUT_TOKENS")
    llm_request_timeout_seconds: float = Field(default=30.0, description="LLM request timeout (seconds)", alias="LLM_REQUEST_TIMEOUT_SECONDS")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env.lower() == "development"
    
    def get_database_url(self, database: str) -> str:
        """Get database URL for specified database."""
        if database == "neo4j":
            return self.neo4j_uri
        elif database == "redis":
            return self.redis_url
        elif database == "postgres":
            return self.postgres_url
        else:
            raise ValueError(f"Unknown database: {database}")
    
    def get_logging_config(self) -> dict:
        """Get logging configuration."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                },
                "json": {
                    "format": '{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json" if self.is_production() else "default",
                    "level": self.log_level.value
                },
                "file": {
                    "class": "logging.FileHandler",
                    "filename": "./logs/app.log",
                    "formatter": "json",
                    "level": self.log_level.value
                }
            },
            "loggers": {
                "": {
                    "handlers": ["console", "file"],
                    "level": self.log_level.value,
                    "propagate": False
                },
                "uvicorn": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False
                },
                "fastapi": {
                    "handlers": ["console"],
                    "level": "INFO",
                    "propagate": False
                }
            }
        }
    
    def get_cors_config(self) -> dict:
        """Get CORS configuration."""
        if self.is_production():
            return {
                "allow_origins": ["https://yourdomain.com"],
                "allow_credentials": True,
                "allow_methods": ["GET", "POST", "PUT", "DELETE"],
                "allow_headers": ["Authorization", "Content-Type"]
            }
        else:
            return {
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"]
            }
    
    def validate_settings(self) -> List[str]:
        """Validate settings and return list of warnings/errors."""
        warnings = []
        
        # Security warnings
        if self.jwt_secret_key == "change-this-secret-key":
            warnings.append("JWT secret key is using default value - change in production")
        
        if self.neo4j_password == "password":
            warnings.append("Neo4j password is using default value - change in production")
        
        # Performance warnings
        if self.max_concurrent_repos > 20:
            warnings.append("High concurrent repository limit may cause resource issues")
        
        if self.max_workers > 8:
            warnings.append("High worker count may cause resource contention")
        
        # Configuration warnings
        if self.is_production() and self.debug:
            warnings.append("Debug mode is enabled in production")
        
        if self.is_production() and not self.auth_enabled:
            warnings.append("Authentication is disabled in production")
        
        return warnings


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global settings
    settings = Settings()
    return settings