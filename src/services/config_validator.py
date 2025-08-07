"""
Configuration Validation Service

Comprehensive validation of environment variables, configuration files,
database connections, and AWS credentials for the GraphRAG system.
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
import socket
from urllib.parse import urlparse

# Third-party imports
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
import psycopg2
from psycopg2 import OperationalError as PostgresError
import redis
from redis.exceptions import ConnectionError as RedisError
import httpx

# Local imports
try:
    from ..config.settings import Settings, get_settings
    from ..core.exceptions import ConfigurationError, ValidationError
except ImportError:
    # Handle case when running as standalone script
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from config.settings import Settings, get_settings
    from core.exceptions import ConfigurationError, ValidationError


class ValidationLevel(str, Enum):
    """Validation severity levels."""
    CRITICAL = "CRITICAL"  # System cannot start
    ERROR = "ERROR"       # Feature will not work
    WARNING = "WARNING"   # Suboptimal configuration
    INFO = "INFO"         # Informational message


@dataclass
class ValidationResult:
    """Result of a configuration validation check."""
    component: str
    check_name: str
    level: ValidationLevel
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    remediation: Optional[str] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


@dataclass
class ValidationSummary:
    """Summary of all validation results."""
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    critical_failures: int = 0
    error_failures: int = 0
    warning_failures: int = 0
    results: List[ValidationResult] = field(default_factory=list)
    overall_success: bool = False
    validation_time: float = 0.0
    
    def add_result(self, result: ValidationResult):
        """Add a validation result to the summary."""
        self.results.append(result)
        self.total_checks += 1
        
        if result.success:
            self.passed_checks += 1
        else:
            self.failed_checks += 1
            if result.level == ValidationLevel.CRITICAL:
                self.critical_failures += 1
            elif result.level == ValidationLevel.ERROR:
                self.error_failures += 1
            elif result.level == ValidationLevel.WARNING:
                self.warning_failures += 1
    
    def finalize(self):
        """Finalize the summary and determine overall success."""
        # System is considered successful if no critical failures
        self.overall_success = self.critical_failures == 0


class ConfigurationValidator:
    """Comprehensive configuration validation service."""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.logger = logging.getLogger(__name__)
        self.summary = ValidationSummary()
    
    async def validate_all(self) -> ValidationSummary:
        """Run all configuration validations."""
        start_time = asyncio.get_event_loop().time()
        
        self.logger.info("Starting comprehensive configuration validation")
        
        # Run all validation categories
        await self._validate_environment_variables()
        await self._validate_configuration_files()
        await self._validate_database_connections()
        await self._validate_aws_credentials()
        await self._validate_service_endpoints()
        await self._validate_file_system_access()
        await self._validate_security_settings()
        await self._validate_performance_settings()
        
        # Finalize summary
        end_time = asyncio.get_event_loop().time()
        self.summary.validation_time = end_time - start_time
        self.summary.finalize()
        
        self.logger.info(
            f"Configuration validation completed in {self.summary.validation_time:.2f}s: "
            f"{self.summary.passed_checks}/{self.summary.total_checks} checks passed"
        )
        
        return self.summary
    
    async def _validate_environment_variables(self):
        """Validate required environment variables."""
        self.logger.debug("Validating environment variables")
        
        # Critical environment variables
        critical_vars = {
            'NEO4J_URI': 'Neo4j database connection URI',
            'NEO4J_USERNAME': 'Neo4j database username',
            'NEO4J_PASSWORD': 'Neo4j database password',
            'CHROMA_HOST': 'ChromaDB host address',
            'CHROMA_PORT': 'ChromaDB port number',
        }
        
        # Optional but recommended variables
        recommended_vars = {
            'POSTGRES_URL': 'PostgreSQL database connection URL',
            'REDIS_URL': 'Redis cache connection URL',
            'AWS_REGION': 'AWS region for Bedrock services',
            'BEDROCK_MODEL_ID': 'AWS Bedrock model identifier',
            'LOG_LEVEL': 'Application logging level',
        }
        
        # Check critical variables
        for var_name, description in critical_vars.items():
            value = os.getenv(var_name)
            if not value:
                self.summary.add_result(ValidationResult(
                    component="Environment",
                    check_name=f"Required variable {var_name}",
                    level=ValidationLevel.CRITICAL,
                    success=False,
                    message=f"Missing required environment variable: {var_name}",
                    details={"variable": var_name, "description": description},
                    remediation=f"Set {var_name} in your .env file or environment"
                ))
            else:
                # Validate format for specific variables
                if var_name == 'NEO4J_URI':
                    if not self._validate_neo4j_uri_format(value):
                        self.summary.add_result(ValidationResult(
                            component="Environment",
                            check_name=f"Format validation {var_name}",
                            level=ValidationLevel.ERROR,
                            success=False,
                            message=f"Invalid Neo4j URI format: {value}",
                            remediation="Use format: bolt://host:port or neo4j://host:port"
                        ))
                    else:
                        self.summary.add_result(ValidationResult(
                            component="Environment",
                            check_name=f"Required variable {var_name}",
                            level=ValidationLevel.INFO,
                            success=True,
                            message=f"Environment variable {var_name} is set and valid"
                        ))
                elif var_name in ['CHROMA_PORT']:
                    if not value.isdigit() or not (1 <= int(value) <= 65535):
                        self.summary.add_result(ValidationResult(
                            component="Environment",
                            check_name=f"Format validation {var_name}",
                            level=ValidationLevel.ERROR,
                            success=False,
                            message=f"Invalid port number: {value}",
                            remediation="Port must be a number between 1 and 65535"
                        ))
                    else:
                        self.summary.add_result(ValidationResult(
                            component="Environment",
                            check_name=f"Required variable {var_name}",
                            level=ValidationLevel.INFO,
                            success=True,
                            message=f"Environment variable {var_name} is set and valid"
                        ))
                else:
                    self.summary.add_result(ValidationResult(
                        component="Environment",
                        check_name=f"Required variable {var_name}",
                        level=ValidationLevel.INFO,
                        success=True,
                        message=f"Environment variable {var_name} is set"
                    ))
        
        # Check recommended variables
        for var_name, description in recommended_vars.items():
            value = os.getenv(var_name)
            if not value:
                self.summary.add_result(ValidationResult(
                    component="Environment",
                    check_name=f"Recommended variable {var_name}",
                    level=ValidationLevel.WARNING,
                    success=False,
                    message=f"Missing recommended environment variable: {var_name}",
                    details={"variable": var_name, "description": description},
                    remediation=f"Consider setting {var_name} for full functionality"
                ))
            else:
                self.summary.add_result(ValidationResult(
                    component="Environment",
                    check_name=f"Recommended variable {var_name}",
                    level=ValidationLevel.INFO,
                    success=True,
                    message=f"Recommended variable {var_name} is set"
                ))
    
    async def _validate_configuration_files(self):
        """Validate configuration files exist and are valid."""
        self.logger.debug("Validating configuration files")
        
        # Check .env file
        env_file = Path(".env")
        if not env_file.exists():
            self.summary.add_result(ValidationResult(
                component="Configuration",
                check_name="Environment file",
                level=ValidationLevel.WARNING,
                success=False,
                message="No .env file found",
                remediation="Copy .env.example to .env and configure your settings"
            ))
        else:
            # Validate .env file format
            try:
                with open(env_file, 'r') as f:
                    content = f.read()
                    # Basic validation - check for common issues
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if '=' not in line:
                                self.summary.add_result(ValidationResult(
                                    component="Configuration",
                                    check_name="Environment file format",
                                    level=ValidationLevel.WARNING,
                                    success=False,
                                    message=f"Invalid line format in .env at line {i}: {line}",
                                    remediation="Use format: VARIABLE=value"
                                ))
                
                self.summary.add_result(ValidationResult(
                    component="Configuration",
                    check_name="Environment file",
                    level=ValidationLevel.INFO,
                    success=True,
                    message="Environment file exists and is readable"
                ))
            except Exception as e:
                self.summary.add_result(ValidationResult(
                    component="Configuration",
                    check_name="Environment file",
                    level=ValidationLevel.ERROR,
                    success=False,
                    message=f"Error reading .env file: {str(e)}",
                    remediation="Check file permissions and format"
                ))
        
        # Check logs directory
        logs_dir = Path("logs")
        if not logs_dir.exists():
            try:
                logs_dir.mkdir(parents=True, exist_ok=True)
                self.summary.add_result(ValidationResult(
                    component="Configuration",
                    check_name="Logs directory",
                    level=ValidationLevel.INFO,
                    success=True,
                    message="Created logs directory"
                ))
            except Exception as e:
                self.summary.add_result(ValidationResult(
                    component="Configuration",
                    check_name="Logs directory",
                    level=ValidationLevel.ERROR,
                    success=False,
                    message=f"Cannot create logs directory: {str(e)}",
                    remediation="Check file system permissions"
                ))
        else:
            self.summary.add_result(ValidationResult(
                component="Configuration",
                check_name="Logs directory",
                level=ValidationLevel.INFO,
                success=True,
                message="Logs directory exists"
            ))
        
        # Check data directory
        data_dir = Path("data")
        if not data_dir.exists():
            try:
                data_dir.mkdir(parents=True, exist_ok=True)
                self.summary.add_result(ValidationResult(
                    component="Configuration",
                    check_name="Data directory",
                    level=ValidationLevel.INFO,
                    success=True,
                    message="Created data directory"
                ))
            except Exception as e:
                self.summary.add_result(ValidationResult(
                    component="Configuration",
                    check_name="Data directory",
                    level=ValidationLevel.ERROR,
                    success=False,
                    message=f"Cannot create data directory: {str(e)}",
                    remediation="Check file system permissions"
                ))
        else:
            self.summary.add_result(ValidationResult(
                component="Configuration",
                check_name="Data directory",
                level=ValidationLevel.INFO,
                success=True,
                message="Data directory exists"
            ))
    
    async def _validate_database_connections(self):
        """Validate database connection strings and connectivity."""
        self.logger.debug("Validating database connections")
        
        # Validate Neo4j connection
        await self._validate_neo4j_connection()
        
        # Validate PostgreSQL connection
        await self._validate_postgresql_connection()
        
        # Validate Redis connection
        await self._validate_redis_connection()
        
        # Validate ChromaDB connection
        await self._validate_chromadb_connection()
    
    async def _validate_neo4j_connection(self):
        """Validate Neo4j database connection."""
        try:
            # Import Neo4j driver dynamically to avoid startup issues
            from neo4j import GraphDatabase
            
            uri = self.settings.neo4j_uri
            username = self.settings.neo4j_username
            password = self.settings.neo4j_password
            
            # Validate URI format
            if not self._validate_neo4j_uri_format(uri):
                self.summary.add_result(ValidationResult(
                    component="Database",
                    check_name="Neo4j URI format",
                    level=ValidationLevel.ERROR,
                    success=False,
                    message=f"Invalid Neo4j URI format: {uri}",
                    remediation="Use format: bolt://host:port or neo4j://host:port"
                ))
                return
            
            # Test connection
            try:
                driver = GraphDatabase.driver(uri, auth=(username, password))
                with driver.session() as session:
                    result = session.run("RETURN 1 as test")
                    test_value = result.single()["test"]
                    if test_value == 1:
                        self.summary.add_result(ValidationResult(
                            component="Database",
                            check_name="Neo4j connectivity",
                            level=ValidationLevel.INFO,
                            success=True,
                            message="Neo4j connection successful"
                        ))
                    else:
                        self.summary.add_result(ValidationResult(
                            component="Database",
                            check_name="Neo4j connectivity",
                            level=ValidationLevel.ERROR,
                            success=False,
                            message="Neo4j connection test failed",
                            remediation="Check Neo4j service status and credentials"
                        ))
                driver.close()
            except Exception as e:
                self.summary.add_result(ValidationResult(
                    component="Database",
                    check_name="Neo4j connectivity",
                    level=ValidationLevel.CRITICAL,
                    success=False,
                    message=f"Neo4j connection failed: {str(e)}",
                    remediation="Check Neo4j service status, credentials, and network connectivity"
                ))
        
        except ImportError:
            self.summary.add_result(ValidationResult(
                component="Database",
                check_name="Neo4j driver",
                level=ValidationLevel.CRITICAL,
                success=False,
                message="Neo4j driver not installed",
                remediation="Install neo4j driver: pip install neo4j"
            ))
    
    async def _validate_postgresql_connection(self):
        """Validate PostgreSQL database connection."""
        try:
            postgres_url = self.settings.postgres_url
            
            # Parse URL
            parsed = urlparse(postgres_url)
            if not all([parsed.scheme, parsed.hostname, parsed.username]):
                self.summary.add_result(ValidationResult(
                    component="Database",
                    check_name="PostgreSQL URL format",
                    level=ValidationLevel.ERROR,
                    success=False,
                    message=f"Invalid PostgreSQL URL format: {postgres_url}",
                    remediation="Use format: postgresql://user:password@host:port/database"
                ))
                return
            
            # Test connection
            try:
                conn = psycopg2.connect(postgres_url)
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    if result and result[0] == 1:
                        self.summary.add_result(ValidationResult(
                            component="Database",
                            check_name="PostgreSQL connectivity",
                            level=ValidationLevel.INFO,
                            success=True,
                            message="PostgreSQL connection successful"
                        ))
                    else:
                        self.summary.add_result(ValidationResult(
                            component="Database",
                            check_name="PostgreSQL connectivity",
                            level=ValidationLevel.ERROR,
                            success=False,
                            message="PostgreSQL connection test failed",
                            remediation="Check PostgreSQL service status and credentials"
                        ))
                conn.close()
            except PostgresError as e:
                self.summary.add_result(ValidationResult(
                    component="Database",
                    check_name="PostgreSQL connectivity",
                    level=ValidationLevel.ERROR,
                    success=False,
                    message=f"PostgreSQL connection failed: {str(e)}",
                    remediation="Check PostgreSQL service status, credentials, and network connectivity"
                ))
        
        except ImportError:
            self.summary.add_result(ValidationResult(
                component="Database",
                check_name="PostgreSQL driver",
                level=ValidationLevel.WARNING,
                success=False,
                message="PostgreSQL driver not installed",
                remediation="Install psycopg2: pip install psycopg2-binary"
            ))
    
    async def _validate_redis_connection(self):
        """Validate Redis connection."""
        try:
            redis_url = self.settings.redis_url
            
            # Parse URL
            parsed = urlparse(redis_url)
            if not parsed.scheme or parsed.scheme != 'redis':
                self.summary.add_result(ValidationResult(
                    component="Database",
                    check_name="Redis URL format",
                    level=ValidationLevel.ERROR,
                    success=False,
                    message=f"Invalid Redis URL format: {redis_url}",
                    remediation="Use format: redis://host:port or redis://user:password@host:port"
                ))
                return
            
            # Test connection
            try:
                r = redis.from_url(redis_url)
                result = r.ping()
                if result:
                    self.summary.add_result(ValidationResult(
                        component="Database",
                        check_name="Redis connectivity",
                        level=ValidationLevel.INFO,
                        success=True,
                        message="Redis connection successful"
                    ))
                else:
                    self.summary.add_result(ValidationResult(
                        component="Database",
                        check_name="Redis connectivity",
                        level=ValidationLevel.ERROR,
                        success=False,
                        message="Redis ping failed",
                        remediation="Check Redis service status"
                    ))
            except RedisError as e:
                self.summary.add_result(ValidationResult(
                    component="Database",
                    check_name="Redis connectivity",
                    level=ValidationLevel.WARNING,
                    success=False,
                    message=f"Redis connection failed: {str(e)}",
                    remediation="Check Redis service status and network connectivity"
                ))
        
        except ImportError:
            self.summary.add_result(ValidationResult(
                component="Database",
                check_name="Redis driver",
                level=ValidationLevel.WARNING,
                success=False,
                message="Redis driver not installed",
                remediation="Install redis: pip install redis"
            ))
    
    async def _validate_chromadb_connection(self):
        """Validate ChromaDB connection."""
        try:
            chroma_host = self.settings.chroma_host
            chroma_port = self.settings.chroma_port
            
            # Test HTTP connection to ChromaDB API
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        f"http://{chroma_host}:{chroma_port}/api/v2/heartbeat",
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        self.summary.add_result(ValidationResult(
                            component="Database",
                            check_name="ChromaDB connectivity",
                            level=ValidationLevel.INFO,
                            success=True,
                            message="ChromaDB connection successful"
                        ))
                    else:
                        self.summary.add_result(ValidationResult(
                            component="Database",
                            check_name="ChromaDB connectivity",
                            level=ValidationLevel.CRITICAL,
                            success=False,
                            message=f"ChromaDB returned status {response.status_code}",
                            remediation="Check ChromaDB service status"
                        ))
                except httpx.RequestError as e:
                    self.summary.add_result(ValidationResult(
                        component="Database",
                        check_name="ChromaDB connectivity",
                        level=ValidationLevel.CRITICAL,
                        success=False,
                        message=f"ChromaDB connection failed: {str(e)}",
                        remediation="Check ChromaDB service status and network connectivity"
                    ))
        
        except Exception as e:
            self.summary.add_result(ValidationResult(
                component="Database",
                check_name="ChromaDB connectivity",
                level=ValidationLevel.CRITICAL,
                success=False,
                message=f"ChromaDB validation error: {str(e)}",
                remediation="Check ChromaDB configuration and dependencies"
            ))
    
    async def _validate_aws_credentials(self):
        """Validate AWS credentials and Bedrock access."""
        self.logger.debug("Validating AWS credentials")
        
        # Check if AWS credentials are configured
        aws_access_key = self.settings.aws_access_key_id
        aws_secret_key = self.settings.aws_secret_access_key
        aws_region = self.settings.aws_region
        bedrock_model_id = self.settings.bedrock_model_id
        
        if not any([aws_access_key, aws_secret_key, aws_region]):
            self.summary.add_result(ValidationResult(
                component="AWS",
                check_name="AWS credentials",
                level=ValidationLevel.WARNING,
                success=False,
                message="AWS credentials not configured",
                remediation="Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION for Bedrock functionality"
            ))
            return
        
        # Validate credential format
        if aws_access_key and not re.match(r'^AKIA[0-9A-Z]{16}$', aws_access_key):
            self.summary.add_result(ValidationResult(
                component="AWS",
                check_name="AWS access key format",
                level=ValidationLevel.ERROR,
                success=False,
                message="Invalid AWS access key format",
                remediation="AWS access keys should start with AKIA and be 20 characters long"
            ))
        
        if aws_secret_key and len(aws_secret_key) != 40:
            self.summary.add_result(ValidationResult(
                component="AWS",
                check_name="AWS secret key format",
                level=ValidationLevel.ERROR,
                success=False,
                message="Invalid AWS secret key format",
                remediation="AWS secret keys should be 40 characters long"
            ))
        
        # Test AWS credentials
        try:
            session = boto3.Session(
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            
            # Test STS to validate credentials
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            
            self.summary.add_result(ValidationResult(
                component="AWS",
                check_name="AWS credentials validation",
                level=ValidationLevel.INFO,
                success=True,
                message=f"AWS credentials valid for account: {identity.get('Account', 'unknown')}",
                details={"account": identity.get('Account'), "user_id": identity.get('UserId')}
            ))
            
            # Test Bedrock access if model ID is configured
            if bedrock_model_id:
                try:
                    bedrock = session.client('bedrock-runtime', region_name=aws_region)
                    
                    # Test with a minimal request
                    test_request = {
                        "modelId": bedrock_model_id,
                        "contentType": "application/json",
                        "accept": "application/json",
                        "body": json.dumps({
                            "anthropic_version": "bedrock-2023-05-31",
                            "max_tokens": 1,
                            "messages": [{"role": "user", "content": "test"}]
                        })
                    }
                    
                    # This will fail if model doesn't exist or no access
                    response = bedrock.invoke_model(**test_request)
                    
                    self.summary.add_result(ValidationResult(
                        component="AWS",
                        check_name="Bedrock model access",
                        level=ValidationLevel.INFO,
                        success=True,
                        message=f"Bedrock model {bedrock_model_id} is accessible"
                    ))
                    
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code == 'ValidationException':
                        self.summary.add_result(ValidationResult(
                            component="AWS",
                            check_name="Bedrock model access",
                            level=ValidationLevel.ERROR,
                            success=False,
                            message=f"Invalid Bedrock model ID: {bedrock_model_id}",
                            remediation="Check the model ID and ensure it's available in your region"
                        ))
                    elif error_code == 'AccessDeniedException':
                        self.summary.add_result(ValidationResult(
                            component="AWS",
                            check_name="Bedrock model access",
                            level=ValidationLevel.ERROR,
                            success=False,
                            message=f"No access to Bedrock model: {bedrock_model_id}",
                            remediation="Request access to the model in AWS Bedrock console"
                        ))
                    else:
                        self.summary.add_result(ValidationResult(
                            component="AWS",
                            check_name="Bedrock model access",
                            level=ValidationLevel.ERROR,
                            success=False,
                            message=f"Bedrock error: {str(e)}",
                            remediation="Check AWS Bedrock service status and permissions"
                        ))
                except Exception as e:
                    self.summary.add_result(ValidationResult(
                        component="AWS",
                        check_name="Bedrock model access",
                        level=ValidationLevel.ERROR,
                        success=False,
                        message=f"Bedrock validation error: {str(e)}",
                        remediation="Check AWS Bedrock configuration and network connectivity"
                    ))
        
        except (NoCredentialsError, PartialCredentialsError) as e:
            self.summary.add_result(ValidationResult(
                component="AWS",
                check_name="AWS credentials validation",
                level=ValidationLevel.ERROR,
                success=False,
                message=f"AWS credentials error: {str(e)}",
                remediation="Configure valid AWS credentials"
            ))
        except ClientError as e:
            self.summary.add_result(ValidationResult(
                component="AWS",
                check_name="AWS credentials validation",
                level=ValidationLevel.ERROR,
                success=False,
                message=f"AWS authentication failed: {str(e)}",
                remediation="Check AWS credentials and permissions"
            ))
        except Exception as e:
            self.summary.add_result(ValidationResult(
                component="AWS",
                check_name="AWS credentials validation",
                level=ValidationLevel.ERROR,
                success=False,
                message=f"AWS validation error: {str(e)}",
                remediation="Check AWS configuration and network connectivity"
            ))
    
    async def _validate_service_endpoints(self):
        """Validate service endpoint accessibility."""
        self.logger.debug("Validating service endpoints")
        
        endpoints = [
            ("API Server", f"http://{self.settings.api_host}:{self.settings.api_port}/api/v1/health/"),
            ("ChromaDB", f"http://{self.settings.chroma_host}:{self.settings.chroma_port}/api/v2/heartbeat"),
        ]
        
        async with httpx.AsyncClient() as client:
            for service_name, url in endpoints:
                try:
                    response = await client.get(url, timeout=10.0)
                    if response.status_code == 200:
                        self.summary.add_result(ValidationResult(
                            component="Services",
                            check_name=f"{service_name} endpoint",
                            level=ValidationLevel.INFO,
                            success=True,
                            message=f"{service_name} endpoint is accessible"
                        ))
                    else:
                        self.summary.add_result(ValidationResult(
                            component="Services",
                            check_name=f"{service_name} endpoint",
                            level=ValidationLevel.ERROR,
                            success=False,
                            message=f"{service_name} returned status {response.status_code}",
                            remediation=f"Check {service_name} service status"
                        ))
                except httpx.RequestError as e:
                    self.summary.add_result(ValidationResult(
                        component="Services",
                        check_name=f"{service_name} endpoint",
                        level=ValidationLevel.ERROR,
                        success=False,
                        message=f"{service_name} endpoint not accessible: {str(e)}",
                        remediation=f"Check {service_name} service status and network connectivity"
                    ))
    
    async def _validate_file_system_access(self):
        """Validate file system access and permissions."""
        self.logger.debug("Validating file system access")
        
        # Check workspace directory
        workspace_dir = Path(self.settings.workspace_dir)
        try:
            workspace_dir.mkdir(parents=True, exist_ok=True)
            # Test write access
            test_file = workspace_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            
            self.summary.add_result(ValidationResult(
                component="FileSystem",
                check_name="Workspace directory access",
                level=ValidationLevel.INFO,
                success=True,
                message=f"Workspace directory is accessible: {workspace_dir}"
            ))
        except Exception as e:
            self.summary.add_result(ValidationResult(
                component="FileSystem",
                check_name="Workspace directory access",
                level=ValidationLevel.CRITICAL,
                success=False,
                message=f"Cannot access workspace directory: {str(e)}",
                remediation="Check file system permissions and disk space"
            ))
        
        # Check ChromaDB persist directory
        chroma_dir = Path(self.settings.chroma_persist_directory)
        try:
            chroma_dir.mkdir(parents=True, exist_ok=True)
            self.summary.add_result(ValidationResult(
                component="FileSystem",
                check_name="ChromaDB persist directory",
                level=ValidationLevel.INFO,
                success=True,
                message=f"ChromaDB persist directory is accessible: {chroma_dir}"
            ))
        except Exception as e:
            self.summary.add_result(ValidationResult(
                component="FileSystem",
                check_name="ChromaDB persist directory",
                level=ValidationLevel.ERROR,
                success=False,
                message=f"Cannot access ChromaDB persist directory: {str(e)}",
                remediation="Check file system permissions for ChromaDB data directory"
            ))
    
    async def _validate_security_settings(self):
        """Validate security-related settings."""
        self.logger.debug("Validating security settings")
        
        # Check JWT secret key
        if self.settings.jwt_secret_key == "change-this-secret-key":
            self.summary.add_result(ValidationResult(
                component="Security",
                check_name="JWT secret key",
                level=ValidationLevel.WARNING,
                success=False,
                message="JWT secret key is using default value",
                remediation="Change JWT_SECRET_KEY to a secure random value in production"
            ))
        elif len(self.settings.jwt_secret_key) < 32:
            self.summary.add_result(ValidationResult(
                component="Security",
                check_name="JWT secret key",
                level=ValidationLevel.WARNING,
                success=False,
                message="JWT secret key is too short",
                remediation="Use a JWT secret key of at least 32 characters"
            ))
        else:
            self.summary.add_result(ValidationResult(
                component="Security",
                check_name="JWT secret key",
                level=ValidationLevel.INFO,
                success=True,
                message="JWT secret key is properly configured"
            ))
        
        # Check Neo4j password
        if self.settings.neo4j_password in ["password", "neo4j", "admin"]:
            self.summary.add_result(ValidationResult(
                component="Security",
                check_name="Neo4j password",
                level=ValidationLevel.WARNING,
                success=False,
                message="Neo4j password is using a common default value",
                remediation="Change Neo4j password to a secure value"
            ))
        else:
            self.summary.add_result(ValidationResult(
                component="Security",
                check_name="Neo4j password",
                level=ValidationLevel.INFO,
                success=True,
                message="Neo4j password appears to be customized"
            ))
        
        # Check production settings
        if self.settings.is_production():
            if self.settings.debug:
                self.summary.add_result(ValidationResult(
                    component="Security",
                    check_name="Production debug mode",
                    level=ValidationLevel.ERROR,
                    success=False,
                    message="Debug mode is enabled in production",
                    remediation="Set DEBUG=false in production environment"
                ))
            
            if not self.settings.auth_enabled:
                self.summary.add_result(ValidationResult(
                    component="Security",
                    check_name="Production authentication",
                    level=ValidationLevel.ERROR,
                    success=False,
                    message="Authentication is disabled in production",
                    remediation="Enable authentication in production environment"
                ))
    
    async def _validate_performance_settings(self):
        """Validate performance-related settings."""
        self.logger.debug("Validating performance settings")
        
        # Check worker settings
        if self.settings.max_workers > 8:
            self.summary.add_result(ValidationResult(
                component="Performance",
                check_name="Worker count",
                level=ValidationLevel.WARNING,
                success=False,
                message=f"High worker count may cause resource contention: {self.settings.max_workers}",
                remediation="Consider reducing MAX_WORKERS for better resource management"
            ))
        
        if self.settings.max_concurrent_repos > 20:
            self.summary.add_result(ValidationResult(
                component="Performance",
                check_name="Concurrent repositories",
                level=ValidationLevel.WARNING,
                success=False,
                message=f"High concurrent repository limit may cause resource issues: {self.settings.max_concurrent_repos}",
                remediation="Consider reducing MAX_CONCURRENT_REPOS for better resource management"
            ))
        
        # Check timeout settings
        if self.settings.timeout_seconds < 60:
            self.summary.add_result(ValidationResult(
                component="Performance",
                check_name="Processing timeout",
                level=ValidationLevel.WARNING,
                success=False,
                message=f"Processing timeout may be too short: {self.settings.timeout_seconds}s",
                remediation="Consider increasing TIMEOUT_SECONDS for large repositories"
            ))
        
        # Check connection pool size
        if self.settings.connection_pool_size < 5:
            self.summary.add_result(ValidationResult(
                component="Performance",
                check_name="Connection pool size",
                level=ValidationLevel.WARNING,
                success=False,
                message=f"Small connection pool may limit performance: {self.settings.connection_pool_size}",
                remediation="Consider increasing CONNECTION_POOL_SIZE for better performance"
            ))
    
    def _validate_neo4j_uri_format(self, uri: str) -> bool:
        """Validate Neo4j URI format."""
        pattern = r'^(bolt|neo4j|bolt\+s|neo4j\+s)://[^:]+:\d+$'
        return bool(re.match(pattern, uri))
    
    def get_validation_report(self) -> str:
        """Generate a human-readable validation report."""
        if not self.summary.results:
            return "No validation results available"
        
        report = []
        report.append("=" * 60)
        report.append("CONFIGURATION VALIDATION REPORT")
        report.append("=" * 60)
        report.append(f"Total checks: {self.summary.total_checks}")
        report.append(f"Passed: {self.summary.passed_checks}")
        report.append(f"Failed: {self.summary.failed_checks}")
        report.append(f"Critical failures: {self.summary.critical_failures}")
        report.append(f"Error failures: {self.summary.error_failures}")
        report.append(f"Warning failures: {self.summary.warning_failures}")
        report.append(f"Validation time: {self.summary.validation_time:.2f}s")
        report.append(f"Overall success: {'YES' if self.summary.overall_success else 'NO'}")
        report.append("")
        
        # Group results by component
        components = {}
        for result in self.summary.results:
            if result.component not in components:
                components[result.component] = []
            components[result.component].append(result)
        
        for component, results in components.items():
            report.append(f"[{component}]")
            report.append("-" * 40)
            
            for result in results:
                status = "✓" if result.success else "✗"
                level_indicator = {
                    ValidationLevel.CRITICAL: "🔴",
                    ValidationLevel.ERROR: "🟠", 
                    ValidationLevel.WARNING: "🟡",
                    ValidationLevel.INFO: "🟢"
                }.get(result.level, "")
                
                report.append(f"  {status} {level_indicator} {result.check_name}")
                report.append(f"    {result.message}")
                
                if not result.success and result.remediation:
                    report.append(f"    💡 {result.remediation}")
                
                report.append("")
            
            report.append("")
        
        return "\n".join(report)


# Convenience function for quick validation
async def validate_configuration(settings: Optional[Settings] = None) -> ValidationSummary:
    """Run comprehensive configuration validation."""
    validator = ConfigurationValidator(settings)
    return await validator.validate_all()


# CLI function for standalone validation
async def main():
    """Main function for CLI usage."""
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    try:
        summary = await validate_configuration()
        validator = ConfigurationValidator()
        validator.summary = summary
        
        print(validator.get_validation_report())
        
        # Exit with error code if validation failed
        sys.exit(0 if summary.overall_success else 1)
        
    except Exception as e:
        print(f"Validation failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())