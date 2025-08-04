"""
Configuration Schema Validation

Defines and validates configuration schemas for the GraphRAG system.
"""

import os
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
import re
from pathlib import Path


class ConfigType(str, Enum):
    """Configuration value types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    URL = "url"
    PATH = "path"
    EMAIL = "email"
    PORT = "port"
    JSON = "json"


@dataclass
class ConfigField:
    """Configuration field definition."""
    name: str
    type: ConfigType
    required: bool = False
    default: Optional[Any] = None
    description: str = ""
    validation_pattern: Optional[str] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    depends_on: Optional[List[str]] = None  # Fields this depends on


class ConfigSchema:
    """Configuration schema definition and validation."""
    
    def __init__(self):
        self.fields = self._define_schema()
    
    def _define_schema(self) -> Dict[str, ConfigField]:
        """Define the complete configuration schema."""
        return {
            # Application settings
            "APP_NAME": ConfigField(
                name="APP_NAME",
                type=ConfigType.STRING,
                default="GraphRAG",
                description="Application name"
            ),
            "APP_ENV": ConfigField(
                name="APP_ENV",
                type=ConfigType.STRING,
                default="development",
                description="Application environment",
                allowed_values=["development", "staging", "production"]
            ),
            "DEBUG": ConfigField(
                name="DEBUG",
                type=ConfigType.BOOLEAN,
                default=False,
                description="Enable debug mode"
            ),
            "LOG_LEVEL": ConfigField(
                name="LOG_LEVEL",
                type=ConfigType.STRING,
                default="INFO",
                description="Logging level",
                allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            ),
            
            # API settings
            "API_HOST": ConfigField(
                name="API_HOST",
                type=ConfigType.STRING,
                default="0.0.0.0",
                description="API server host"
            ),
            "API_PORT": ConfigField(
                name="API_PORT",
                type=ConfigType.PORT,
                default=8080,
                description="API server port",
                min_value=1,
                max_value=65535
            ),
            "API_WORKERS": ConfigField(
                name="API_WORKERS",
                type=ConfigType.INTEGER,
                default=4,
                description="Number of API workers",
                min_value=1,
                max_value=32
            ),
            
            # ChromaDB settings
            "CHROMA_HOST": ConfigField(
                name="CHROMA_HOST",
                type=ConfigType.STRING,
                required=True,
                description="ChromaDB host address"
            ),
            "CHROMA_PORT": ConfigField(
                name="CHROMA_PORT",
                type=ConfigType.PORT,
                required=True,
                description="ChromaDB port number",
                min_value=1,
                max_value=65535
            ),
            "CHROMA_COLLECTION_NAME": ConfigField(
                name="CHROMA_COLLECTION_NAME",
                type=ConfigType.STRING,
                default="codebase_chunks",
                description="ChromaDB collection name"
            ),
            "CHROMA_PERSIST_DIRECTORY": ConfigField(
                name="CHROMA_PERSIST_DIRECTORY",
                type=ConfigType.PATH,
                default="./data/chroma",
                description="ChromaDB persistence directory"
            ),
            
            # Neo4j settings
            "NEO4J_URI": ConfigField(
                name="NEO4J_URI",
                type=ConfigType.URL,
                required=True,
                description="Neo4j connection URI",
                validation_pattern=r"^(bolt|neo4j|bolt\+s|neo4j\+s)://[^:]+:\d+$"
            ),
            "NEO4J_USERNAME": ConfigField(
                name="NEO4J_USERNAME",
                type=ConfigType.STRING,
                required=True,
                description="Neo4j username"
            ),
            "NEO4J_PASSWORD": ConfigField(
                name="NEO4J_PASSWORD",
                type=ConfigType.STRING,
                required=True,
                description="Neo4j password"
            ),
            "NEO4J_DATABASE": ConfigField(
                name="NEO4J_DATABASE",
                type=ConfigType.STRING,
                default="neo4j",
                description="Neo4j database name"
            ),
            
            # Redis settings
            "REDIS_URL": ConfigField(
                name="REDIS_URL",
                type=ConfigType.URL,
                default="redis://localhost:6379",
                description="Redis connection URL",
                validation_pattern=r"^redis://[^:]+:\d+$"
            ),
            "REDIS_PASSWORD": ConfigField(
                name="REDIS_PASSWORD",
                type=ConfigType.STRING,
                description="Redis password"
            ),
            
            # PostgreSQL settings
            "POSTGRES_URL": ConfigField(
                name="POSTGRES_URL",
                type=ConfigType.URL,
                description="PostgreSQL connection URL",
                validation_pattern=r"^postgresql://[^:]+:[^@]+@[^:]+:\d+/\w+$"
            ),
            
            # MinIO settings
            "MINIO_ENDPOINT": ConfigField(
                name="MINIO_ENDPOINT",
                type=ConfigType.STRING,
                default="localhost:9000",
                description="MinIO endpoint"
            ),
            "MINIO_ACCESS_KEY": ConfigField(
                name="MINIO_ACCESS_KEY",
                type=ConfigType.STRING,
                default="minioadmin",
                description="MinIO access key"
            ),
            "MINIO_SECRET_KEY": ConfigField(
                name="MINIO_SECRET_KEY",
                type=ConfigType.STRING,
                default="minioadmin",
                description="MinIO secret key"
            ),
            "MINIO_SECURE": ConfigField(
                name="MINIO_SECURE",
                type=ConfigType.BOOLEAN,
                default=False,
                description="Use secure connection to MinIO"
            ),
            
            # AWS Bedrock settings
            "AWS_REGION": ConfigField(
                name="AWS_REGION",
                type=ConfigType.STRING,
                description="AWS region for Bedrock services",
                validation_pattern=r"^[a-z]{2}-[a-z]+-\d+$"
            ),
            "AWS_ACCESS_KEY_ID": ConfigField(
                name="AWS_ACCESS_KEY_ID",
                type=ConfigType.STRING,
                description="AWS access key ID",
                validation_pattern=r"^AKIA[0-9A-Z]{16}$",
                depends_on=["AWS_SECRET_ACCESS_KEY", "AWS_REGION"]
            ),
            "AWS_SECRET_ACCESS_KEY": ConfigField(
                name="AWS_SECRET_ACCESS_KEY",
                type=ConfigType.STRING,
                description="AWS secret access key",
                depends_on=["AWS_ACCESS_KEY_ID", "AWS_REGION"]
            ),
            "BEDROCK_MODEL_ID": ConfigField(
                name="BEDROCK_MODEL_ID",
                type=ConfigType.STRING,
                description="AWS Bedrock model identifier",
                depends_on=["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]
            ),
            
            # Embedding settings
            "EMBEDDING_MODEL": ConfigField(
                name="EMBEDDING_MODEL",
                type=ConfigType.STRING,
                default="sentence-transformers/all-MiniLM-L6-v2",
                description="Embedding model name"
            ),
            "EMBEDDING_DIMENSION": ConfigField(
                name="EMBEDDING_DIMENSION",
                type=ConfigType.INTEGER,
                default=384,
                description="Embedding dimension",
                min_value=1,
                max_value=4096
            ),
            "EMBEDDING_DEVICE": ConfigField(
                name="EMBEDDING_DEVICE",
                type=ConfigType.STRING,
                default="cpu",
                description="Device for embedding computation",
                allowed_values=["cpu", "cuda", "mps"]
            ),
            
            # Processing settings
            "MAX_CONCURRENT_REPOS": ConfigField(
                name="MAX_CONCURRENT_REPOS",
                type=ConfigType.INTEGER,
                default=10,
                description="Maximum concurrent repositories",
                min_value=1,
                max_value=100
            ),
            "MAX_WORKERS": ConfigField(
                name="MAX_WORKERS",
                type=ConfigType.INTEGER,
                default=4,
                description="Maximum worker processes",
                min_value=1,
                max_value=32
            ),
            "BATCH_SIZE": ConfigField(
                name="BATCH_SIZE",
                type=ConfigType.INTEGER,
                default=100,
                description="Processing batch size",
                min_value=1,
                max_value=10000
            ),
            "TIMEOUT_SECONDS": ConfigField(
                name="TIMEOUT_SECONDS",
                type=ConfigType.INTEGER,
                default=300,
                description="Processing timeout in seconds",
                min_value=10,
                max_value=3600
            ),
            
            # Security settings
            "AUTH_ENABLED": ConfigField(
                name="AUTH_ENABLED",
                type=ConfigType.BOOLEAN,
                default=False,
                description="Enable authentication"
            ),
            "JWT_SECRET_KEY": ConfigField(
                name="JWT_SECRET_KEY",
                type=ConfigType.STRING,
                default="change-this-secret-key",
                description="JWT secret key"
            ),
            "JWT_ALGORITHM": ConfigField(
                name="JWT_ALGORITHM",
                type=ConfigType.STRING,
                default="HS256",
                description="JWT algorithm",
                allowed_values=["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
            ),
            "JWT_EXPIRATION_HOURS": ConfigField(
                name="JWT_EXPIRATION_HOURS",
                type=ConfigType.INTEGER,
                default=24,
                description="JWT expiration in hours",
                min_value=1,
                max_value=8760  # 1 year
            ),
            
            # File system settings
            "WORKSPACE_DIR": ConfigField(
                name="WORKSPACE_DIR",
                type=ConfigType.PATH,
                default="./data/repositories",
                description="Repository workspace directory"
            ),
            "MAX_FILE_SIZE": ConfigField(
                name="MAX_FILE_SIZE",
                type=ConfigType.INTEGER,
                default=1048576,  # 1MB
                description="Maximum file size in bytes",
                min_value=1024,
                max_value=104857600  # 100MB
            ),
        }
    
    def validate_value(self, field: ConfigField, value: Any) -> tuple[bool, Optional[str]]:
        """Validate a single configuration value."""
        if value is None:
            if field.required:
                return False, f"Required field {field.name} is missing"
            return True, None
        
        # Type validation
        if field.type == ConfigType.STRING:
            if not isinstance(value, str):
                return False, f"{field.name} must be a string"
        
        elif field.type == ConfigType.INTEGER:
            try:
                int_value = int(value)
                if field.min_value is not None and int_value < field.min_value:
                    return False, f"{field.name} must be >= {field.min_value}"
                if field.max_value is not None and int_value > field.max_value:
                    return False, f"{field.name} must be <= {field.max_value}"
            except (ValueError, TypeError):
                return False, f"{field.name} must be an integer"
        
        elif field.type == ConfigType.FLOAT:
            try:
                float_value = float(value)
                if field.min_value is not None and float_value < field.min_value:
                    return False, f"{field.name} must be >= {field.min_value}"
                if field.max_value is not None and float_value > field.max_value:
                    return False, f"{field.name} must be <= {field.max_value}"
            except (ValueError, TypeError):
                return False, f"{field.name} must be a number"
        
        elif field.type == ConfigType.BOOLEAN:
            if isinstance(value, str):
                if value.lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                    return False, f"{field.name} must be a boolean (true/false)"
            elif not isinstance(value, bool):
                return False, f"{field.name} must be a boolean"
        
        elif field.type == ConfigType.PORT:
            try:
                port_value = int(value)
                if not (1 <= port_value <= 65535):
                    return False, f"{field.name} must be a valid port number (1-65535)"
            except (ValueError, TypeError):
                return False, f"{field.name} must be a valid port number"
        
        elif field.type == ConfigType.URL:
            if not isinstance(value, str):
                return False, f"{field.name} must be a URL string"
            # Basic URL validation - could be enhanced
            if not (value.startswith('http://') or value.startswith('https://') or 
                   value.startswith('bolt://') or value.startswith('neo4j://') or
                   value.startswith('redis://') or value.startswith('postgresql://')):
                return False, f"{field.name} must be a valid URL"
        
        elif field.type == ConfigType.PATH:
            if not isinstance(value, str):
                return False, f"{field.name} must be a path string"
            # Basic path validation
            try:
                Path(value)
            except Exception:
                return False, f"{field.name} must be a valid path"
        
        elif field.type == ConfigType.EMAIL:
            if not isinstance(value, str):
                return False, f"{field.name} must be an email string"
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, value):
                return False, f"{field.name} must be a valid email address"
        
        elif field.type == ConfigType.JSON:
            if isinstance(value, str):
                try:
                    json.loads(value)
                except json.JSONDecodeError:
                    return False, f"{field.name} must be valid JSON"
        
        # Pattern validation
        if field.validation_pattern and isinstance(value, str):
            if not re.match(field.validation_pattern, value):
                return False, f"{field.name} does not match required pattern"
        
        # Allowed values validation
        if field.allowed_values and value not in field.allowed_values:
            return False, f"{field.name} must be one of: {', '.join(map(str, field.allowed_values))}"
        
        return True, None
    
    def validate_dependencies(self, config: Dict[str, Any]) -> List[str]:
        """Validate field dependencies."""
        errors = []
        
        for field_name, field in self.fields.items():
            if field.depends_on:
                field_value = config.get(field_name)
                if field_value:  # If this field is set
                    # Check if all dependencies are also set
                    for dep in field.depends_on:
                        if not config.get(dep):
                            errors.append(
                                f"{field_name} requires {dep} to be set"
                            )
        
        return errors
    
    def validate_configuration(self, config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate complete configuration."""
        errors = []
        
        # Validate individual fields
        for field_name, field in self.fields.items():
            value = config.get(field_name)
            is_valid, error = self.validate_value(field, value)
            if not is_valid:
                errors.append(error)
        
        # Validate dependencies
        dependency_errors = self.validate_dependencies(config)
        errors.extend(dependency_errors)
        
        return len(errors) == 0, errors
    
    def get_field_info(self, field_name: str) -> Optional[ConfigField]:
        """Get information about a specific field."""
        return self.fields.get(field_name)
    
    def get_required_fields(self) -> List[str]:
        """Get list of required field names."""
        return [name for name, field in self.fields.items() if field.required]
    
    def get_optional_fields(self) -> List[str]:
        """Get list of optional field names."""
        return [name for name, field in self.fields.items() if not field.required]
    
    def generate_env_template(self) -> str:
        """Generate a .env template file with all fields."""
        lines = []
        lines.append("# GraphRAG Configuration Template")
        lines.append("# Copy this file to .env and update with your settings")
        lines.append("")
        
        # Group fields by category
        categories = {
            "Application": ["APP_NAME", "APP_ENV", "DEBUG", "LOG_LEVEL"],
            "API": ["API_HOST", "API_PORT", "API_WORKERS"],
            "ChromaDB": ["CHROMA_HOST", "CHROMA_PORT", "CHROMA_COLLECTION_NAME", "CHROMA_PERSIST_DIRECTORY"],
            "Neo4j": ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE"],
            "Redis": ["REDIS_URL", "REDIS_PASSWORD"],
            "PostgreSQL": ["POSTGRES_URL"],
            "MinIO": ["MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_SECURE"],
            "AWS Bedrock": ["AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "BEDROCK_MODEL_ID"],
            "Embedding": ["EMBEDDING_MODEL", "EMBEDDING_DIMENSION", "EMBEDDING_DEVICE"],
            "Processing": ["MAX_CONCURRENT_REPOS", "MAX_WORKERS", "BATCH_SIZE", "TIMEOUT_SECONDS"],
            "Security": ["AUTH_ENABLED", "JWT_SECRET_KEY", "JWT_ALGORITHM", "JWT_EXPIRATION_HOURS"],
            "File System": ["WORKSPACE_DIR", "MAX_FILE_SIZE"]
        }
        
        for category, field_names in categories.items():
            lines.append(f"# {category} Settings")
            for field_name in field_names:
                field = self.fields.get(field_name)
                if field:
                    lines.append(f"# {field.description}")
                    if field.required:
                        lines.append(f"# REQUIRED")
                    if field.default is not None:
                        lines.append(f"{field_name}={field.default}")
                    else:
                        lines.append(f"# {field_name}=")
                    lines.append("")
            lines.append("")
        
        return "\n".join(lines)


# Global schema instance
config_schema = ConfigSchema()


def validate_env_file(env_file_path: str = ".env") -> tuple[bool, List[str]]:
    """Validate configuration from .env file."""
    if not os.path.exists(env_file_path):
        return False, [f"Environment file {env_file_path} not found"]
    
    config = {}
    
    # Load environment variables from file
    with open(env_file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
                else:
                    return False, [f"Invalid line format at line {line_num}: {line}"]
    
    # Also include actual environment variables (they override .env)
    for key in config_schema.fields.keys():
        env_value = os.getenv(key)
        if env_value is not None:
            config[key] = env_value
    
    return config_schema.validate_configuration(config)


def generate_env_template(output_file: str = ".env.template") -> None:
    """Generate environment template file."""
    template = config_schema.generate_env_template()
    with open(output_file, 'w') as f:
        f.write(template)
    print(f"Environment template generated: {output_file}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "generate-template":
        generate_env_template()
    else:
        # Validate current configuration
        is_valid, errors = validate_env_file()
        
        if is_valid:
            print("✅ Configuration validation passed")
            sys.exit(0)
        else:
            print("❌ Configuration validation failed:")
            for error in errors:
                print(f"  • {error}")
            sys.exit(1)