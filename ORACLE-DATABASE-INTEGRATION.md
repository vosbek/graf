# 🗄️ Oracle Database Integration for Legacy System Analysis

## Overview

Legacy applications often store critical business rules and data mappings directly in Oracle databases. To fully answer the "golden questions" about data flow and business logic, we need to integrate Oracle database schema and business rules into our RAG pipeline.

## Current Gap Analysis

### **What We Have Now**
- ✅ **Code Analysis**: JSP, Struts Actions, CORBA interfaces
- ✅ **Static Relationships**: Code dependencies and calls
- ✅ **Business Rules**: Extracted from Java/JSP validation logic

### **What We're Missing**
- ❌ **Database Schema**: Table structures, relationships, constraints
- ❌ **Stored Procedures**: Business logic in PL/SQL
- ❌ **Data Flow Tracing**: JSP field → SQL query → Oracle table
- ❌ **Business Rules in DB**: Triggers, constraints, lookup tables

### **Golden Questions We Can't Answer Yet**
- **"Where does the 'Specified Amount' field get its data from?"** 
  - Need to trace: JSP input → Action → DAO → SQL → Oracle table/column
- **"What determines the display value for contract type?"**
  - Need to discover: Oracle lookup tables, business rule procedures
- **Account Information queries** 
  - Need to map: JSP displays → Database views/tables

## Proposed Oracle Integration Architecture

### **Phase 1: Oracle Schema Ingestion**

```
Oracle Database (Read-Only)
    ↓
Schema Discovery Service
    ↓
Oracle Database Analyzer
    ↓
├── Table Metadata → Neo4j (DatabaseTable nodes)
├── Column Metadata → Neo4j (DatabaseColumn nodes)  
├── Stored Procedures → ChromaDB (Embedded PL/SQL)
├── Views & Triggers → ChromaDB (Business logic)
└── Constraints → Neo4j (BusinessRule nodes)
```

### **Phase 2: Data Flow Analysis**

```
Code Analysis (Current)     Oracle Analysis (New)
    ↓                           ↓
Struts Action               SQL Query Detection
    ↓                           ↓
JDBC/DAO calls       →      Table/Column Mapping
    ↓                           ↓
    Neo4j Relationship: QUERIES_TABLE
```

### **Phase 3: Enhanced Chat Integration**

```
User Query: "Where does Amount field get data?"
    ↓
Enhanced ChatAgent
    ↓
├── ChromaDB: Find JSP with "Amount" field
├── Neo4j: Trace JSP → Action → DAO relationship  
├── Oracle Tool: Find SQL queries for Amount
└── Response: "Amount field from contract_details.specified_amount"
```

## Implementation Plan

### **Step 1: Add Oracle Database Client**

Create `src/core/oracle_client.py`:

```python
import cx_Oracle
from typing import Dict, List, Any, Optional
from ..config.settings import settings

class OracleDBClient:
    """Read-only Oracle database client for schema analysis."""
    
    def __init__(self):
        self.connection_string = settings.oracle_connection_string
        self.username = settings.oracle_username
        self.password = settings.oracle_password
        
    async def get_table_schema(self, schema_name: str) -> List[Dict[str, Any]]:
        """Get all tables and columns for a schema."""
        
    async def get_stored_procedures(self, schema_name: str) -> List[Dict[str, Any]]:
        """Get stored procedures and functions with PL/SQL source."""
        
    async def get_triggers(self, schema_name: str) -> List[Dict[str, Any]]:
        """Get database triggers (often contain business rules)."""
        
    async def get_constraints(self, schema_name: str) -> List[Dict[str, Any]]:
        """Get check constraints, foreign keys (business rules)."""
```

### **Step 2: Oracle Database Analyzer**

Create `src/services/oracle_analyzer.py`:

```python
from typing import Dict, List, Any
from ..core.oracle_client import OracleDBClient
from ..core.neo4j_client import Neo4jClient
from ..core.chromadb_client import ChromaDBClient

class OracleDatabaseAnalyzer:
    """Analyzes Oracle database schema and business logic."""
    
    async def analyze_database_schema(self, schema_names: List[str]) -> Dict[str, Any]:
        """
        Analyze Oracle schema and create:
        - Neo4j nodes for tables, columns, procedures
        - ChromaDB embeddings for PL/SQL business logic
        - Relationships between code and database objects
        """
        
    async def extract_business_rules_from_plsql(self, procedure_source: str) -> List[Dict[str, Any]]:
        """Extract business rules from PL/SQL procedures."""
        
    async def find_sql_queries_in_code(self, repository_name: str) -> List[Dict[str, Any]]:
        """Find SQL queries in Java/JSP code and map to Oracle objects."""
```

### **Step 3: Enhanced Neo4j Schema**

Add Oracle database node types:

```cypher
// Database Schema Nodes
CREATE CONSTRAINT database_table_name IF NOT EXISTS FOR (t:DatabaseTable) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT database_column_name IF NOT EXISTS FOR (c:DatabaseColumn) REQUIRE (c.table_name, c.column_name) IS UNIQUE;
CREATE CONSTRAINT stored_procedure_name IF NOT EXISTS FOR (p:StoredProcedure) REQUIRE p.name IS UNIQUE;

// Relationships
(:StrutsAction)-[:QUERIES_TABLE]->(:DatabaseTable)
(:JSPComponent)-[:DISPLAYS_COLUMN]->(:DatabaseColumn)
(:DatabaseTable)-[:HAS_COLUMN]->(:DatabaseColumn)
(:StoredProcedure)-[:CONTAINS_BUSINESS_RULE]->(:BusinessRule)
```

### **Step 4: Strands Oracle Tool**

Create `strands/tools/oracle_tool.py`:

```python
class OracleTool:
    """Oracle database query tool for the chat agent."""
    
    def __init__(self, oracle_client: Any):
        self._client = oracle_client
        
    async def find_data_source(self, field_name: str, context: str) -> Dict[str, Any]:
        """
        Find Oracle table/column that provides data for a field.
        
        Args:
            field_name: e.g., "specified_amount", "contract_type"
            context: e.g., "Universal Life", "Account Information"
            
        Returns:
            {
                "table": "contract_details",
                "column": "specified_amount", 
                "business_rules": ["amount > 0", "amount <= max_coverage"],
                "related_procedures": ["calculate_premium", "validate_amount"]
            }
        """
        
    async def trace_data_flow(self, jsp_field: str, repository: str) -> List[Dict[str, Any]]:
        """
        Trace data flow from JSP field back to Oracle source.
        
        Returns path: JSP → Action → DAO → SQL → Oracle Table/Column
        """
```

### **Step 5: Configuration Updates**

Add to `.env`:

```env
# Oracle Database Configuration (Read-Only Access)
ORACLE_CONNECTION_STRING=localhost:1521/XE
ORACLE_USERNAME=readonly_user
ORACLE_PASSWORD=readonly_password
ORACLE_SCHEMAS=INSURANCE,CONTRACTS,CUSTOMER

# Oracle Integration Settings
ORACLE_ENABLED=true
ORACLE_SCHEMA_CACHE_TTL=3600
ORACLE_MAX_CONNECTIONS=5
```

## Data Flow Tracing Implementation

### **Enhanced Business Rule Detection**

```python
class EnhancedBusinessRuleExtractor:
    """Extract business rules from multiple sources."""
    
    async def extract_from_all_sources(self, repository_name: str) -> List[BusinessRule]:
        rules = []
        
        # Existing: Java/JSP validation logic
        rules.extend(await self.extract_from_java_code())
        
        # NEW: Oracle stored procedures
        rules.extend(await self.extract_from_plsql_procedures())
        
        # NEW: Database constraints  
        rules.extend(await self.extract_from_db_constraints())
        
        # NEW: Trigger logic
        rules.extend(await self.extract_from_triggers())
        
        return rules
```

### **SQL Query Detection in Code**

```python
class SQLQueryDetector:
    """Detect and parse SQL queries in Java/JSP code."""
    
    def find_sql_in_java(self, java_code: str) -> List[Dict[str, Any]]:
        """
        Find SQL queries in Java code:
        - PreparedStatement queries
        - String concatenated SQL
        - MyBatis/Hibernate queries
        """
        
    def extract_table_references(self, sql_query: str) -> List[str]:
        """Extract table names from SQL queries."""
        
    def map_java_fields_to_sql_columns(self, java_class: str, sql_queries: List[str]) -> Dict[str, str]:
        """Map Java getter/setter fields to SQL column names."""
```

## Enhanced Chat Agent Integration

### **Updated ChatAgent with Oracle Context**

```python
# In strands/agents/chat_agent.py
class ChatAgent:
    def __init__(self, chroma_tool, neo4j_tool, oracle_tool, llm_provider, settings):
        # Add oracle_tool to existing tools
        self._oracle_tool = oracle_tool
        
    async def _handle_data_source_questions(self, question: str) -> Dict[str, Any]:
        """
        Handle questions about data sources:
        - "Where does X field get its data?"
        - "What table contains Y data?"
        - "How is Z calculated?"
        """
        
        # 1. Find JSP/UI components mentioning the field
        ui_components = await self._chroma_tool.semantic_search(
            f"JSP field input {field_name}", top_k=5
        )
        
        # 2. Trace through Neo4j relationships
        data_flow = await self._neo4j_tool.trace_data_flow(field_name)
        
        # 3. Find Oracle source using Oracle tool
        oracle_source = await self._oracle_tool.find_data_source(field_name, context)
        
        # 4. Combine into comprehensive answer
        return self._format_data_source_response(ui_components, data_flow, oracle_source)
```

## Golden Questions Implementation

### **Question 1: "What JSP contains the code that displays Account Information for Universal Life contracts?"**

**Enhanced Answer Path:**
1. **ChromaDB**: Search for JSP files with "Account Information" + "Universal Life"
2. **Neo4j**: Find JSP components with business_domain="insurance" 
3. **Oracle**: Check for related tables (account_info, universal_life_contracts)
4. **Response**: "account_info.jsp displays data from CONTRACTS.UNIVERSAL_LIFE_ACCOUNTS table via AccountInfoAction"

### **Question 2: "Where does the 'Specified Amount' field get its data from?"**

**Enhanced Answer Path:**
1. **ChromaDB**: Find JSP/forms with "Specified Amount" input field
2. **Neo4j**: Trace JSP → Action → DAO relationships
3. **Oracle**: Find SQL queries and map to CONTRACTS.specified_amount column
4. **Oracle**: Check business rules in stored procedures (validate_amount, calculate_premium)
5. **Response**: "Specified Amount from CONTRACT_DETAILS.SPECIFIED_AMOUNT, validated by validate_contract_amount() procedure"

### **Question 3: "What determines the display value for contract type?"**

**Enhanced Answer Path:**
1. **ChromaDB**: Find code handling "contract type" display logic
2. **Neo4j**: Find business rules for contract type formatting
3. **Oracle**: Check LOOKUP_CONTRACT_TYPES table and display_format procedures
4. **Response**: "Contract type display determined by format_contract_type() procedure using LOOKUP_CONTRACT_TYPES.display_name"

## Implementation Priority

### **Phase 1 (High Priority): Basic Oracle Integration**
- Oracle client and connection management
- Schema discovery and table/column mapping
- Basic SQL query detection in Java code
- Neo4j schema extension for database objects

### **Phase 2 (Medium Priority): Business Rule Integration**  
- PL/SQL procedure analysis and embedding
- Database constraint extraction
- Trigger business rule detection
- Enhanced data flow tracing

### **Phase 3 (Low Priority): Advanced Features**
- Real-time Oracle query execution for chat
- Data lineage visualization
- Performance optimization for large schemas
- Oracle-specific migration recommendations

## Configuration Requirements

### **Oracle Database Access**
- **Read-only database user** with SELECT privileges
- **Schema access** to business application schemas
- **Network connectivity** from GraphRAG system to Oracle
- **JDBC driver** (cx_Oracle or oracledb Python package)

### **Security Considerations**
- Use dedicated read-only user with minimal privileges
- Store Oracle credentials securely (not in .env for production)
- Audit database access logs
- Implement connection pooling and rate limiting

## Expected Benefits

### **Enhanced Golden Question Answers**
- **Complete data lineage**: JSP → Action → DAO → SQL → Oracle table/column
- **Business rule discovery**: Find validation logic in PL/SQL procedures
- **Data source identification**: Precisely identify where fields get their data
- **Migration planning**: Understand database dependencies for modernization

### **Improved Chat Responses**
- **Specific data sources**: "Field X comes from table Y, column Z"
- **Business rule context**: "Amount validated by procedure P with rules R1, R2"
- **Migration guidance**: "Replace Oracle lookup with GraphQL enum/resolver"
- **Complete system understanding**: Full stack visibility from UI to database

---

**This Oracle integration will transform our system from code-only analysis to complete legacy system understanding, enabling precise answers to data lineage and business logic questions.**