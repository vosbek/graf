"""
Oracle Database Client for Legacy System Analysis
===============================================

Read-only Oracle database client for analyzing database schema,
stored procedures, and business rules in legacy applications.

This client provides:
- Schema discovery (tables, columns, constraints)
- PL/SQL procedure and function analysis
- Business rule extraction from database objects
- SQL query mapping and data lineage support
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
import time

from ..config.settings import Settings
from .exceptions import DatabaseError, ConnectionError as GraphRAGConnectionError

logger = logging.getLogger(__name__)

# Lazy import to avoid dependency issues if Oracle is not configured
try:
    import cx_Oracle
    ORACLE_AVAILABLE = True
except ImportError:
    try:
        import oracledb as cx_Oracle
        ORACLE_AVAILABLE = True
    except ImportError:
        cx_Oracle = None
        ORACLE_AVAILABLE = False


@dataclass
class OracleTableMetadata:
    """Oracle table metadata."""
    schema_name: str
    table_name: str
    table_type: str  # TABLE, VIEW
    comments: Optional[str] = None
    row_count: Optional[int] = None


@dataclass 
class OracleColumnMetadata:
    """Oracle column metadata."""
    schema_name: str
    table_name: str
    column_name: str
    data_type: str
    nullable: bool
    default_value: Optional[str] = None
    comments: Optional[str] = None
    business_purpose: Optional[str] = None  # Derived from comments/naming


@dataclass
class OracleStoredProcedure:
    """Oracle stored procedure metadata."""
    schema_name: str
    object_name: str
    object_type: str  # PROCEDURE, FUNCTION, PACKAGE
    source_code: str
    parameters: List[Dict[str, Any]]
    business_rules: List[str]  # Extracted business logic


@dataclass
class OracleConstraint:
    """Oracle constraint metadata."""
    schema_name: str
    table_name: str
    constraint_name: str
    constraint_type: str  # PRIMARY KEY, FOREIGN KEY, CHECK, UNIQUE
    condition: Optional[str] = None
    referenced_table: Optional[str] = None
    business_rule: Optional[str] = None  # Interpreted business meaning


class OracleDBClient:
    """
    Oracle database client for legacy system analysis.
    
    Provides read-only access to Oracle databases for:
    - Schema discovery and metadata extraction
    - Business rule identification in PL/SQL
    - Data lineage analysis
    - Integration with Neo4j and ChromaDB
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._connection_pool: Optional[Any] = None
        self._thread_pool = ThreadPoolExecutor(max_workers=5)
        
        # Oracle connection configuration
        self.enabled = getattr(settings, 'oracle_enabled', False)
        self.connection_string = getattr(settings, 'oracle_connection_string', None)
        self.username = getattr(settings, 'oracle_username', None)
        self.password = getattr(settings, 'oracle_password', None)
        self.schemas = getattr(settings, 'oracle_schemas', 'USER').split(',')
        
        # Performance settings
        self.max_connections = getattr(settings, 'oracle_max_connections', 5)
        self.cache_ttl = getattr(settings, 'oracle_schema_cache_ttl', 3600)
        
        # Schema cache
        self._schema_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        
        if not ORACLE_AVAILABLE and self.enabled:
            logger.warning("Oracle client requested but cx_Oracle/oracledb not available")
            self.enabled = False
    
    async def initialize(self) -> None:
        """Initialize Oracle connection pool."""
        if not self.enabled or not ORACLE_AVAILABLE:
            logger.info("Oracle client disabled or not available")
            return
            
        if not all([self.connection_string, self.username, self.password]):
            logger.warning("Oracle credentials not configured - disabling Oracle client")
            self.enabled = False
            return
            
        try:
            # Initialize connection pool in thread pool
            loop = asyncio.get_event_loop()
            self._connection_pool = await loop.run_in_executor(
                self._thread_pool,
                self._create_connection_pool
            )
            logger.info(f"Oracle connection pool initialized for schemas: {self.schemas}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Oracle connection pool: {e}")
            self.enabled = False
            raise DatabaseError(f"Oracle initialization failed: {e}")
    
    def _create_connection_pool(self) -> Any:
        """Create Oracle connection pool (runs in thread pool)."""
        return cx_Oracle.create_pool(
            user=self.username,
            password=self.password,
            dsn=self.connection_string,
            min=1,
            max=self.max_connections,
            increment=1,
            threaded=True,
            encoding='UTF-8'
        )
    
    @asynccontextmanager
    async def _get_connection(self) -> AsyncGenerator[Any, None]:
        """Get connection from pool."""
        if not self.enabled or not self._connection_pool:
            raise GraphRAGConnectionError("Oracle client not initialized or disabled")
            
        connection = None
        try:
            loop = asyncio.get_event_loop()
            connection = await loop.run_in_executor(
                self._thread_pool,
                self._connection_pool.acquire
            )
            yield connection
            
        except Exception as e:
            logger.error(f"Oracle connection error: {e}")
            raise DatabaseError(f"Oracle connection failed: {e}")
            
        finally:
            if connection:
                try:
                    await loop.run_in_executor(
                        self._thread_pool,
                        self._connection_pool.release,
                        connection
                    )
                except Exception as e:
                    logger.error(f"Error releasing Oracle connection: {e}")
    
    async def _execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute read-only query and return results."""
        if not self.enabled:
            return []
            
        async with self._get_connection() as connection:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._thread_pool,
                self._execute_query_sync,
                connection,
                query,
                parameters or {}
            )
    
    def _execute_query_sync(self, connection: Any, query: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute query synchronously (runs in thread pool)."""
        cursor = connection.cursor()
        try:
            cursor.execute(query, parameters)
            columns = [col[0].lower() for col in cursor.description]
            rows = cursor.fetchall()
            
            return [dict(zip(columns, row)) for row in rows]
            
        finally:
            cursor.close()
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._cache_timestamps:
            return False
        return time.time() - self._cache_timestamps[cache_key] < self.cache_ttl
    
    def _cache_result(self, cache_key: str, result: Any) -> None:
        """Cache query result."""
        self._schema_cache[cache_key] = result
        self._cache_timestamps[cache_key] = time.time()
    
    async def get_table_schema(self, schema_name: str) -> List[OracleTableMetadata]:
        """
        Get all tables and views for a schema.
        
        Args:
            schema_name: Oracle schema name
            
        Returns:
            List of table metadata objects
        """
        if not self.enabled:
            return []
            
        cache_key = f"tables_{schema_name}"
        if self._is_cache_valid(cache_key):
            cached_data = self._schema_cache[cache_key]
            return [OracleTableMetadata(**item) for item in cached_data]
        
        query = """
        SELECT 
            owner as schema_name,
            table_name,
            'TABLE' as table_type,
            comments,
            num_rows as row_count
        FROM all_tables 
        WHERE owner = :schema_name
        
        UNION ALL
        
        SELECT 
            owner as schema_name,
            view_name as table_name,
            'VIEW' as table_type,
            null as comments,
            null as row_count
        FROM all_views 
        WHERE owner = :schema_name
        
        ORDER BY table_name
        """
        
        try:
            results = await self._execute_query(query, {'schema_name': schema_name.upper()})
            
            # Cache results
            self._cache_result(cache_key, results)
            
            return [OracleTableMetadata(**row) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get table schema for {schema_name}: {e}")
            return []
    
    async def get_column_metadata(self, schema_name: str, table_name: Optional[str] = None) -> List[OracleColumnMetadata]:
        """
        Get column metadata for tables in schema.
        
        Args:
            schema_name: Oracle schema name
            table_name: Optional specific table name
            
        Returns:
            List of column metadata objects
        """
        if not self.enabled:
            return []
            
        cache_key = f"columns_{schema_name}_{table_name or 'all'}"
        if self._is_cache_valid(cache_key):
            cached_data = self._schema_cache[cache_key]
            return [OracleColumnMetadata(**item) for item in cached_data]
        
        query = """
        SELECT 
            c.owner as schema_name,
            c.table_name,
            c.column_name,
            c.data_type,
            CASE WHEN c.nullable = 'Y' THEN 1 ELSE 0 END as nullable,
            c.data_default as default_value,
            cc.comments,
            CASE 
                WHEN UPPER(c.column_name) LIKE '%AMOUNT%' THEN 'Financial amount field'
                WHEN UPPER(c.column_name) LIKE '%TYPE%' THEN 'Classification/category field'
                WHEN UPPER(c.column_name) LIKE '%STATUS%' THEN 'Status indicator field'
                WHEN UPPER(c.column_name) LIKE '%DATE%' THEN 'Date/timestamp field'
                WHEN UPPER(c.column_name) LIKE '%ID' THEN 'Identifier field'
                ELSE null
            END as business_purpose
        FROM all_tab_columns c
        LEFT JOIN all_col_comments cc ON c.owner = cc.owner 
            AND c.table_name = cc.table_name 
            AND c.column_name = cc.column_name
        WHERE c.owner = :schema_name
        """
        
        parameters = {'schema_name': schema_name.upper()}
        
        if table_name:
            query += " AND c.table_name = :table_name"
            parameters['table_name'] = table_name.upper()
            
        query += " ORDER BY c.table_name, c.column_id"
        
        try:
            results = await self._execute_query(query, parameters)
            
            # Cache results
            self._cache_result(cache_key, results)
            
            return [OracleColumnMetadata(**row) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get column metadata for {schema_name}: {e}")
            return []
    
    async def get_stored_procedures(self, schema_name: str) -> List[OracleStoredProcedure]:
        """
        Get stored procedures and functions with source code.
        
        Args:
            schema_name: Oracle schema name
            
        Returns:
            List of stored procedure metadata
        """
        if not self.enabled:
            return []
            
        cache_key = f"procedures_{schema_name}"
        if self._is_cache_valid(cache_key):
            cached_data = self._schema_cache[cache_key]
            return [OracleStoredProcedure(**item) for item in cached_data]
        
        # Get procedure metadata
        metadata_query = """
        SELECT 
            owner as schema_name,
            object_name,
            object_type
        FROM all_objects 
        WHERE owner = :schema_name 
            AND object_type IN ('PROCEDURE', 'FUNCTION', 'PACKAGE')
            AND status = 'VALID'
        ORDER BY object_name
        """
        
        try:
            metadata_results = await self._execute_query(metadata_query, {'schema_name': schema_name.upper()})
            procedures = []
            
            for metadata in metadata_results:
                # Get source code for each procedure
                source_query = """
                SELECT text 
                FROM all_source 
                WHERE owner = :schema_name 
                    AND name = :object_name 
                    AND type = :object_type
                ORDER BY line
                """
                
                source_results = await self._execute_query(source_query, {
                    'schema_name': schema_name.upper(),
                    'object_name': metadata['object_name'],
                    'object_type': metadata['object_type']
                })
                
                source_code = ''.join([row['text'] for row in source_results])
                
                # Extract business rules from PL/SQL (simplified)
                business_rules = self._extract_business_rules_from_plsql(source_code)
                
                procedures.append(OracleStoredProcedure(
                    schema_name=metadata['schema_name'],
                    object_name=metadata['object_name'],
                    object_type=metadata['object_type'],
                    source_code=source_code,
                    parameters=[],  # TODO: Extract parameters
                    business_rules=business_rules
                ))
            
            # Cache results  
            cache_data = [
                {
                    'schema_name': p.schema_name,
                    'object_name': p.object_name,
                    'object_type': p.object_type,
                    'source_code': p.source_code,
                    'parameters': p.parameters,
                    'business_rules': p.business_rules
                }
                for p in procedures
            ]
            self._cache_result(cache_key, cache_data)
            
            return procedures
            
        except Exception as e:
            logger.error(f"Failed to get stored procedures for {schema_name}: {e}")
            return []
    
    def _extract_business_rules_from_plsql(self, source_code: str) -> List[str]:
        """Extract business rules from PL/SQL source code."""
        business_rules = []
        
        # Simple pattern matching for common business rule patterns
        patterns = [
            r'IF\s+([^THEN]+)\s+THEN',  # IF conditions
            r'CHECK\s*\(\s*([^)]+)\s*\)',  # CHECK constraints
            r'WHEN\s+([^THEN]+)\s+THEN',  # CASE/WHEN conditions
            r'RAISE_APPLICATION_ERROR\s*\(\s*-?\d+\s*,\s*[\'"]([^\'"]+)[\'"]',  # Error messages
        ]
        
        import re
        for pattern in patterns:
            matches = re.findall(pattern, source_code, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ''
                rule = match.strip()
                if rule and len(rule) > 10:  # Filter out trivial matches
                    business_rules.append(rule)
        
        return business_rules[:10]  # Limit to top 10 rules per procedure
    
    async def get_constraints(self, schema_name: str, table_name: Optional[str] = None) -> List[OracleConstraint]:
        """
        Get database constraints (business rules).
        
        Args:
            schema_name: Oracle schema name
            table_name: Optional specific table name
            
        Returns:
            List of constraint metadata
        """
        if not self.enabled:
            return []
            
        query = """
        SELECT 
            c.owner as schema_name,
            c.table_name,
            c.constraint_name,
            c.constraint_type,
            c.search_condition as condition,
            r.table_name as referenced_table,
            CASE c.constraint_type
                WHEN 'C' THEN 'CHECK constraint: ' || c.search_condition
                WHEN 'P' THEN 'Primary key constraint'
                WHEN 'R' THEN 'Foreign key to ' || r.table_name
                WHEN 'U' THEN 'Unique constraint'
                ELSE 'Other constraint'
            END as business_rule
        FROM all_constraints c
        LEFT JOIN all_constraints r ON c.r_constraint_name = r.constraint_name 
            AND c.r_owner = r.owner
        WHERE c.owner = :schema_name
            AND c.constraint_type IN ('C', 'P', 'R', 'U')
            AND c.constraint_name NOT LIKE 'SYS_%'
        """
        
        parameters = {'schema_name': schema_name.upper()}
        
        if table_name:
            query += " AND c.table_name = :table_name"
            parameters['table_name'] = table_name.upper()
            
        query += " ORDER BY c.table_name, c.constraint_name"
        
        try:
            results = await self._execute_query(query, parameters)
            return [OracleConstraint(**row) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get constraints for {schema_name}: {e}")
            return []
    
    async def find_tables_by_pattern(self, schema_name: str, pattern: str) -> List[OracleTableMetadata]:
        """
        Find tables matching a name pattern.
        
        Args:
            schema_name: Oracle schema name  
            pattern: SQL LIKE pattern (e.g., '%ACCOUNT%', '%CONTRACT%')
            
        Returns:
            List of matching tables
        """
        if not self.enabled:
            return []
            
        query = """
        SELECT 
            owner as schema_name,
            table_name,
            'TABLE' as table_type,
            comments,
            num_rows as row_count
        FROM all_tables 
        WHERE owner = :schema_name 
            AND UPPER(table_name) LIKE UPPER(:pattern)
        ORDER BY table_name
        """
        
        try:
            results = await self._execute_query(query, {
                'schema_name': schema_name.upper(),
                'pattern': pattern
            })
            
            return [OracleTableMetadata(**row) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to find tables by pattern {pattern}: {e}")
            return []
    
    async def find_columns_by_pattern(self, schema_name: str, pattern: str) -> List[OracleColumnMetadata]:
        """
        Find columns matching a name pattern across all tables.
        
        Args:
            schema_name: Oracle schema name
            pattern: SQL LIKE pattern (e.g., '%AMOUNT%', '%TYPE%')
            
        Returns:
            List of matching columns
        """
        if not self.enabled:
            return []
            
        query = """
        SELECT 
            c.owner as schema_name,
            c.table_name,
            c.column_name,
            c.data_type,
            CASE WHEN c.nullable = 'Y' THEN 1 ELSE 0 END as nullable,
            c.data_default as default_value,
            cc.comments,
            'Pattern match: ' || :pattern as business_purpose
        FROM all_tab_columns c
        LEFT JOIN all_col_comments cc ON c.owner = cc.owner 
            AND c.table_name = cc.table_name 
            AND c.column_name = cc.column_name
        WHERE c.owner = :schema_name
            AND UPPER(c.column_name) LIKE UPPER(:pattern)
        ORDER BY c.table_name, c.column_name
        """
        
        try:
            results = await self._execute_query(query, {
                'schema_name': schema_name.upper(),
                'pattern': pattern
            })
            
            return [OracleColumnMetadata(**row) for row in results]
            
        except Exception as e:
            logger.error(f"Failed to find columns by pattern {pattern}: {e}")
            return []
    
    async def test_connection(self) -> bool:
        """Test Oracle database connection."""
        if not self.enabled:
            return False
            
        try:
            await self._execute_query("SELECT 1 FROM dual")
            return True
        except Exception as e:
            logger.error(f"Oracle connection test failed: {e}")
            return False
    
    async def close(self) -> None:
        """Close Oracle connection pool."""
        if self._connection_pool:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self._thread_pool,
                    self._connection_pool.close
                )
                logger.info("Oracle connection pool closed")
            except Exception as e:
                logger.error(f"Error closing Oracle connection pool: {e}")
        
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)


# Export main classes
__all__ = [
    'OracleDBClient',
    'OracleTableMetadata', 
    'OracleColumnMetadata',
    'OracleStoredProcedure',
    'OracleConstraint',
    'ORACLE_AVAILABLE'
]