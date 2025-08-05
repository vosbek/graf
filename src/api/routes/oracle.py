"""
Oracle Database Integration API Routes
=====================================

Provides endpoints for Oracle database analysis and data source discovery
for legacy system migration and golden question answering.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...dependencies import get_oracle_client, get_oracle_analyzer
from ...config.settings import settings

router = APIRouter()

# Request/Response Models

class DataSourceRequest(BaseModel):
    field_name: str = Field(..., description="Field name to find data source for")
    context: Optional[str] = Field(default="", description="Business context (e.g., 'Universal Life', 'Account')")

class DataSourceInfo(BaseModel):
    table: str
    column: str
    schema: str
    business_purpose: str
    data_type: str
    nullable: bool
    table_context: str

class DataSourceResponse(BaseModel):
    field_name: str
    data_sources: List[DataSourceInfo]
    business_rules: List[str]
    related_procedures: List[str]
    confidence: float
    status: str

class SchemaAnalysisRequest(BaseModel):
    schema_names: List[str] = Field(..., description="Oracle schema names to analyze")

class SchemaAnalysisResponse(BaseModel):
    status: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DomainTablesRequest(BaseModel):
    domain: str = Field(..., description="Business domain (e.g., 'account', 'contract', 'customer')")

class DomainTable(BaseModel):
    schema: str
    table: str
    type: str
    comments: Optional[str]
    row_count: Optional[int]
    business_domain: str

class DomainTablesResponse(BaseModel):
    domain: str
    tables: List[DomainTable]

class CodeMappingRequest(BaseModel):
    repository_name: str = Field(..., description="Repository to analyze for code-to-database mappings")

class CodeMappingResponse(BaseModel):
    status: str
    repository: str
    sql_queries_found: int
    mappings_created: int
    error: Optional[str] = None

# Oracle Health Check

@router.get("/health")
async def oracle_health_check(
    oracle_client: Any = Depends(get_oracle_client)
):
    """Check Oracle database connection and integration status."""
    if not oracle_client.enabled:
        return {
            "status": "disabled",
            "message": "Oracle integration is disabled",
            "enabled": False
        }
    
    try:
        # Test connection and get basic stats
        connection_status = await oracle_client.test_connection()
        
        return {
            "status": "healthy",
            "enabled": True,
            "schemas": oracle_client.schemas,
            "max_connections": oracle_client.max_connections,
            "connection_test": connection_status
        }
    except Exception as e:
        return {
            "status": "error", 
            "enabled": True,
            "error": str(e)
        }

# Data Source Discovery

@router.post("/data-source", response_model=DataSourceResponse)
async def find_data_source(
    request: DataSourceRequest,
    oracle_client: Any = Depends(get_oracle_client)
):
    """
    Find Oracle table/column that provides data for a specific field.
    
    This is the core endpoint for answering "golden questions" like:
    "Where does the 'Specified Amount' field get its data from?"
    """
    if not oracle_client.enabled:
        raise HTTPException(
            status_code=503, 
            detail="Oracle integration is disabled"
        )
    
    try:
        from strands.tools.oracle_tool import OracleTool
        oracle_tool = OracleTool(oracle_client)
        
        result = await oracle_tool.find_data_source(
            field_name=request.field_name,
            context=request.context
        )
        
        # Convert to response model
        data_sources = [
            DataSourceInfo(
                table=source['table'],
                column=source['column'], 
                schema=source['schema'],
                business_purpose=source['business_purpose'],
                data_type=source['data_type'],
                nullable=source.get('nullable', True),
                table_context=source.get('table_context', 'business_data')
            )
            for source in result.get('data_sources', [])
        ]
        
        return DataSourceResponse(
            field_name=result['field_name'],
            data_sources=data_sources,
            business_rules=result.get('business_rules', []),
            related_procedures=result.get('related_procedures', []),
            confidence=result.get('confidence', 0.0),
            status=result.get('status', 'success')
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data source discovery failed: {str(e)}"
        )

# Schema Analysis

@router.post("/analyze-schemas", response_model=SchemaAnalysisResponse)
async def analyze_oracle_schemas(
    request: SchemaAnalysisRequest,
    oracle_analyzer: Any = Depends(get_oracle_analyzer)
):
    """
    Analyze Oracle database schemas and integrate with Neo4j/ChromaDB.
    
    Creates Neo4j nodes for tables, columns, constraints, and procedures.
    Embeds PL/SQL business logic in ChromaDB for semantic search.
    """
    try:
        result = await oracle_analyzer.analyze_database_schemas(request.schema_names)
        
        return SchemaAnalysisResponse(
            status=result['status'],
            results=result.get('results'),
            error=result.get('error')
        )
        
    except Exception as e:
        return SchemaAnalysisResponse(
            status="error",
            error=str(e)
        )

# Domain Tables Discovery

@router.post("/domain-tables", response_model=DomainTablesResponse)
async def get_domain_tables(
    request: DomainTablesRequest,
    oracle_client: Any = Depends(get_oracle_client)
):
    """
    Get Oracle tables related to a specific business domain.
    
    Useful for understanding database structure by business area.
    """
    if not oracle_client.enabled:
        raise HTTPException(
            status_code=503,
            detail="Oracle integration is disabled"
        )
    
    try:
        from strands.tools.oracle_tool import OracleTool
        oracle_tool = OracleTool(oracle_client)
        
        tables_data = await oracle_tool.get_business_domain_tables(request.domain)
        
        tables = [
            DomainTable(
                schema=table['schema'],
                table=table['table'],
                type=table['type'],
                comments=table.get('comments'),
                row_count=table.get('row_count'),
                business_domain=table['business_domain']
            )
            for table in tables_data
        ]
        
        return DomainTablesResponse(
            domain=request.domain,
            tables=tables
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Domain tables discovery failed: {str(e)}"
        )

# Code-to-Database Mapping

@router.post("/code-mapping", response_model=CodeMappingResponse)
async def create_code_database_mapping(
    request: CodeMappingRequest,
    oracle_analyzer: Any = Depends(get_oracle_analyzer)
):
    """
    Create mappings between application code and Oracle database objects.
    
    Analyzes repository code to find SQL queries and creates relationships
    between code chunks and Oracle tables in Neo4j.
    """
    try:
        result = await oracle_analyzer.create_code_to_database_mappings(
            request.repository_name
        )
        
        return CodeMappingResponse(
            status=result['status'],
            repository=result.get('repository', request.repository_name),
            sql_queries_found=result.get('sql_queries_found', 0),
            mappings_created=result.get('mappings_created', 0),
            error=result.get('error')
        )
        
    except Exception as e:
        return CodeMappingResponse(
            status="error",
            repository=request.repository_name,
            sql_queries_found=0,
            mappings_created=0,
            error=str(e)
        )

# Oracle Configuration

@router.get("/config")
async def get_oracle_config():
    """Get current Oracle integration configuration."""
    oracle_config = {
        "enabled": getattr(settings, 'oracle_enabled', False),
        "schemas": getattr(settings, 'oracle_schemas', 'USER').split(','),
        "max_connections": getattr(settings, 'oracle_max_connections', 5),
        "schema_cache_ttl": getattr(settings, 'oracle_schema_cache_ttl', 3600)
    }
    
    # Don't expose sensitive connection details
    if oracle_config['enabled']:
        oracle_config["connection_configured"] = bool(
            getattr(settings, 'oracle_connection_string', None) and
            getattr(settings, 'oracle_username', None)
        )
    
    return oracle_config

# Table Access Validation

@router.get("/validate-table")
async def validate_table_access(
    table_name: str = Query(..., description="Oracle table name"),
    schema_name: str = Query(..., description="Oracle schema name"),
    oracle_client: Any = Depends(get_oracle_client)
):
    """
    Validate that a specific Oracle table is accessible.
    
    Useful for testing permissions and table existence.
    """
    if not oracle_client.enabled:
        raise HTTPException(
            status_code=503,
            detail="Oracle integration is disabled"
        )
    
    try:
        from strands.tools.oracle_tool import OracleTool
        oracle_tool = OracleTool(oracle_client)
        
        is_accessible = await oracle_tool.validate_table_access(table_name, schema_name)
        
        return {
            "table_name": table_name,
            "schema_name": schema_name,
            "accessible": is_accessible,
            "full_name": f"{schema_name}.{table_name}"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Table validation failed: {str(e)}"
        )

# Export router
__all__ = ['router']