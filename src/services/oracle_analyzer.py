"""
Oracle Database Analyzer for Legacy System Analysis
==================================================

Analyzes Oracle database schema and business logic for integration
with the GraphRAG codebase analysis system.

This analyzer:
- Extracts database schema and relationships
- Identifies business rules in PL/SQL procedures
- Maps SQL queries in code to database objects  
- Creates Neo4j nodes for database components
- Embeds PL/SQL business logic in ChromaDB
"""

import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Any, Tuple
import hashlib

from ..core.oracle_client import (
    OracleDBClient, OracleTableMetadata, OracleColumnMetadata, 
    OracleStoredProcedure, OracleConstraint, ORACLE_AVAILABLE
)
from ..core.neo4j_client import Neo4jClient, GraphQuery
from ..core.chromadb_client import ChromaDBClient
from ..core.exceptions import ProcessingError, DatabaseError
from ..processing.code_chunker import EnhancedChunk

logger = logging.getLogger(__name__)


@dataclass
class SQLQuery:
    """Represents a SQL query found in application code."""
    repository: str
    file_path: str
    line_number: int
    query_text: str
    query_type: str  # SELECT, INSERT, UPDATE, DELETE
    tables_referenced: List[str]
    columns_referenced: List[str]
    business_context: Optional[str] = None


@dataclass
class DataFlowMapping:
    """Represents data flow from UI to database."""
    ui_component: str  # JSP file, form field
    action_class: str  # Struts action
    dao_method: str   # Data access method
    sql_queries: List[SQLQuery]
    oracle_objects: List[str]  # Tables/procedures accessed
    business_purpose: str


class OracleDatabaseAnalyzer:
    """
    Analyzes Oracle database schema and integrates with GraphRAG system.
    
    Creates comprehensive mapping between application code and database
    to support golden questions about data sources and business logic.
    """
    
    def __init__(self, oracle_client: OracleDBClient, neo4j_client: Neo4jClient, 
                 chroma_client: ChromaDBClient):
        self.oracle_client = oracle_client
        self.neo4j_client = neo4j_client
        self.chroma_client = chroma_client
        
        # SQL query patterns for different frameworks
        self.sql_patterns = [
            # JDBC PreparedStatement patterns
            r'prepareStatement\s*\(\s*["\']([^"\']+)["\']',
            r'createStatement\s*\(\s*\)\s*\.executeQuery\s*\(\s*["\']([^"\']+)["\']',
            
            # String concatenated SQL
            r'String\s+\w+\s*=\s*["\']([^"\']*SELECT[^"\']+)["\']',
            r'String\s+\w+\s*=\s*["\']([^"\']*INSERT[^"\']+)["\']',
            r'String\s+\w+\s*=\s*["\']([^"\']*UPDATE[^"\']+)["\']',
            r'String\s+\w+\s*=\s*["\']([^"\']*DELETE[^"\']+)["\']',
            
            # MyBatis/iBatis patterns
            r'@Select\s*\(\s*["\']([^"\']+)["\']',
            r'@Insert\s*\(\s*["\']([^"\']+)["\']',
            r'@Update\s*\(\s*["\']([^"\']+)["\']',
            r'@Delete\s*\(\s*["\']([^"\']+)["\']',
            
            # Hibernate HQL (convert to SQL for analysis)
            r'createQuery\s*\(\s*["\']([^"\']+)["\']',
        ]
        
        # Common table name patterns in legacy apps
        self.business_table_patterns = {
            'account': ['%ACCOUNT%', '%ACCT%'],
            'customer': ['%CUSTOMER%', '%CUST%'],
            'contract': ['%CONTRACT%', '%CNTRCT%'],
            'policy': ['%POLICY%', '%PLCY%'],
            'claim': ['%CLAIM%', '%CLM%'],
            'payment': ['%PAYMENT%', '%PMT%'],
            'transaction': ['%TRANSACTION%', '%TXN%'],
            'lookup': ['%LOOKUP%', '%LU_%', '%CODE%']
        }
    
    async def analyze_database_schemas(self, schema_names: List[str]) -> Dict[str, Any]:
        """
        Analyze Oracle database schemas and create Neo4j nodes.
        
        Args:
            schema_names: List of Oracle schema names to analyze
            
        Returns:
            Analysis results with counts and status
        """
        if not ORACLE_AVAILABLE or not self.oracle_client.enabled:
            logger.warning("Oracle integration disabled - skipping database analysis")
            return {"status": "skipped", "reason": "Oracle not available or disabled"}
        
        logger.info(f"Starting Oracle database analysis for schemas: {schema_names}")
        
        results = {
            "schemas_analyzed": 0,
            "tables_created": 0,
            "columns_created": 0,
            "procedures_embedded": 0,
            "constraints_created": 0,
            "relationships_created": 0,
            "business_rules_extracted": 0
        }
        
        try:
            # Create Oracle database nodes in Neo4j
            await self._create_oracle_schema_nodes()
            
            for schema_name in schema_names:
                logger.info(f"Analyzing Oracle schema: {schema_name}")
                
                # 1. Analyze tables and columns
                table_results = await self._analyze_tables_and_columns(schema_name)
                results["tables_created"] += table_results["tables"]
                results["columns_created"] += table_results["columns"]
                
                # 2. Analyze stored procedures and functions
                procedure_results = await self._analyze_stored_procedures(schema_name)
                results["procedures_embedded"] += procedure_results["procedures"]
                results["business_rules_extracted"] += procedure_results["business_rules"]
                
                # 3. Analyze constraints (business rules)
                constraint_results = await self._analyze_constraints(schema_name)
                results["constraints_created"] += constraint_results["constraints"]
                
                # 4. Create relationships between database objects
                relationship_results = await self._create_database_relationships(schema_name)
                results["relationships_created"] += relationship_results["relationships"]
                
                results["schemas_analyzed"] += 1
                
            logger.info(f"Oracle database analysis completed: {results}")
            return {"status": "completed", "results": results}
            
        except Exception as e:
            logger.error(f"Oracle database analysis failed: {e}")
            return {"status": "error", "error": str(e), "partial_results": results}
    
    async def _create_oracle_schema_nodes(self) -> None:
        """Create Neo4j schema for Oracle database objects."""
        logger.info("Creating Oracle database schema in Neo4j")
        
        schema_queries = [
            # Database table nodes
            "CREATE CONSTRAINT oracle_table_unique IF NOT EXISTS FOR (t:OracleTable) REQUIRE (t.schema_name, t.table_name) IS UNIQUE",
            
            # Database column nodes  
            "CREATE CONSTRAINT oracle_column_unique IF NOT EXISTS FOR (c:OracleColumn) REQUIRE (c.schema_name, c.table_name, c.column_name) IS UNIQUE",
            
            # Stored procedure nodes
            "CREATE CONSTRAINT oracle_procedure_unique IF NOT EXISTS FOR (p:OracleProcedure) REQUIRE (p.schema_name, p.object_name) IS UNIQUE",
            
            # Database constraint nodes
            "CREATE CONSTRAINT oracle_constraint_unique IF NOT EXISTS FOR (con:OracleConstraint) REQUIRE (con.schema_name, con.constraint_name) IS UNIQUE",
            
            # Index for performance
            "CREATE INDEX oracle_table_name_idx IF NOT EXISTS FOR (t:OracleTable) ON (t.table_name)",
            "CREATE INDEX oracle_column_name_idx IF NOT EXISTS FOR (c:OracleColumn) ON (c.column_name)",
        ]
        
        for query_text in schema_queries:
            try:
                query = GraphQuery(cypher=query_text, read_only=False)
                await self.neo4j_client.execute_query(query)
            except Exception as e:
                logger.warning(f"Schema creation query failed (may already exist): {e}")
    
    async def _analyze_tables_and_columns(self, schema_name: str) -> Dict[str, int]:
        """Analyze tables and columns for a schema."""
        logger.debug(f"Analyzing tables and columns for schema: {schema_name}")
        
        # Get table metadata
        tables = await self.oracle_client.get_table_schema(schema_name)
        columns = await self.oracle_client.get_column_metadata(schema_name)
        
        tables_created = 0
        columns_created = 0
        
        # Create table nodes
        for table in tables:
            try:
                # Determine business domain based on table name
                business_domain = self._classify_table_business_domain(table.table_name)
                
                query = GraphQuery(
                    cypher="""
                    MERGE (t:OracleTable {schema_name: $schema_name, table_name: $table_name})
                    SET t.table_type = $table_type,
                        t.comments = $comments,
                        t.row_count = $row_count,
                        t.business_domain = $business_domain,
                        t.analyzed_at = datetime()
                    """,
                    parameters={
                        "schema_name": table.schema_name,
                        "table_name": table.table_name,
                        "table_type": table.table_type,
                        "comments": table.comments,
                        "row_count": table.row_count,
                        "business_domain": business_domain
                    },
                    read_only=False
                )
                
                await self.neo4j_client.execute_query(query)
                tables_created += 1
                
            except Exception as e:
                logger.error(f"Failed to create table node for {table.table_name}: {e}")
        
        # Create column nodes and relationships
        for column in columns:
            try:
                query = GraphQuery(
                    cypher="""
                    MERGE (c:OracleColumn {schema_name: $schema_name, table_name: $table_name, column_name: $column_name})
                    SET c.data_type = $data_type,
                        c.nullable = $nullable,
                        c.default_value = $default_value,
                        c.comments = $comments,
                        c.business_purpose = $business_purpose,
                        c.analyzed_at = datetime()
                    
                    WITH c
                    MATCH (t:OracleTable {schema_name: $schema_name, table_name: $table_name})
                    MERGE (t)-[:HAS_COLUMN]->(c)
                    """,
                    parameters={
                        "schema_name": column.schema_name,
                        "table_name": column.table_name,
                        "column_name": column.column_name,
                        "data_type": column.data_type,
                        "nullable": column.nullable,
                        "default_value": column.default_value,
                        "comments": column.comments,
                        "business_purpose": column.business_purpose
                    },
                    read_only=False
                )
                
                await self.neo4j_client.execute_query(query)
                columns_created += 1
                
            except Exception as e:
                logger.error(f"Failed to create column node for {column.column_name}: {e}")
        
        return {"tables": tables_created, "columns": columns_created}
    
    def _classify_table_business_domain(self, table_name: str) -> str:
        """Classify table into business domain based on name."""
        table_upper = table_name.upper()
        
        for domain, patterns in self.business_table_patterns.items():
            for pattern in patterns:
                if pattern.replace('%', '') in table_upper:
                    return domain
        
        # Default domain classification
        if any(x in table_upper for x in ['LOOKUP', 'CODE', 'REF']):
            return 'reference_data'
        elif any(x in table_upper for x in ['LOG', 'AUDIT', 'HISTORY']):
            return 'audit_log'
        else:
            return 'business_data'
    
    async def _analyze_stored_procedures(self, schema_name: str) -> Dict[str, int]:
        """Analyze stored procedures and embed in ChromaDB."""
        logger.debug(f"Analyzing stored procedures for schema: {schema_name}")
        
        procedures = await self.oracle_client.get_stored_procedures(schema_name)
        
        procedures_created = 0
        business_rules_extracted = 0
        chunks_to_embed = []
        
        for procedure in procedures:
            try:
                # Create Neo4j node
                query = GraphQuery(
                    cypher="""
                    MERGE (p:OracleProcedure {schema_name: $schema_name, object_name: $object_name})
                    SET p.object_type = $object_type,
                        p.business_rules_count = $business_rules_count,
                        p.source_length = $source_length,
                        p.analyzed_at = datetime()
                    """,
                    parameters={
                        "schema_name": procedure.schema_name,
                        "object_name": procedure.object_name,
                        "object_type": procedure.object_type,
                        "business_rules_count": len(procedure.business_rules),
                        "source_length": len(procedure.source_code)
                    },
                    read_only=False
                )
                
                await self.neo4j_client.execute_query(query)
                procedures_created += 1
                
                # Create business rule nodes for extracted rules
                for i, rule in enumerate(procedure.business_rules):
                    try:
                        rule_query = GraphQuery(
                            cypher="""
                            MERGE (br:BusinessRule {
                                source: 'oracle_procedure',
                                source_object: $source_object,
                                rule_text: $rule_text
                            })
                            SET br.domain = 'database_logic',
                                br.complexity = 'medium',
                                br.rule_type = 'validation',
                                br.analyzed_at = datetime()
                            
                            WITH br
                            MATCH (p:OracleProcedure {schema_name: $schema_name, object_name: $object_name})
                            MERGE (p)-[:CONTAINS_BUSINESS_RULE]->(br)
                            """,
                            parameters={
                                "source_object": f"{procedure.schema_name}.{procedure.object_name}",
                                "rule_text": rule,
                                "schema_name": procedure.schema_name,
                                "object_name": procedure.object_name
                            },
                            read_only=False
                        )
                        
                        await self.neo4j_client.execute_query(rule_query)
                        business_rules_extracted += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to create business rule for {procedure.object_name}: {e}")
                
                # Prepare for ChromaDB embedding
                if procedure.source_code and len(procedure.source_code.strip()) > 50:
                    chunk = EnhancedChunk(
                        chunk_id=f"oracle_proc_{hashlib.md5(f'{procedure.schema_name}.{procedure.object_name}'.encode()).hexdigest()}",
                        content=procedure.source_code,
                        file_path=f"oracle://{procedure.schema_name}/{procedure.object_name}",
                        language="plsql",
                        metadata={
                            "source_type": "oracle_procedure",
                            "schema_name": procedure.schema_name,
                            "object_name": procedure.object_name,
                            "object_type": procedure.object_type.lower(),
                            "business_rules_count": len(procedure.business_rules),
                            "business_domain": "database_logic"
                        }
                    )
                    chunks_to_embed.append(chunk)
                
            except Exception as e:
                logger.error(f"Failed to analyze procedure {procedure.object_name}: {e}")
        
        # Embed PL/SQL procedures in ChromaDB
        if chunks_to_embed:
            try:
                await self._embed_oracle_chunks(chunks_to_embed)
                logger.info(f"Embedded {len(chunks_to_embed)} Oracle procedures in ChromaDB")
            except Exception as e:
                logger.error(f"Failed to embed Oracle procedures: {e}")
        
        return {"procedures": procedures_created, "business_rules": business_rules_extracted}
    
    async def _embed_oracle_chunks(self, chunks: List[EnhancedChunk]) -> None:
        """Embed Oracle database chunks in ChromaDB."""
        try:
            # Prepare documents for embedding
            documents = []
            metadatas = []
            ids = []
            
            for chunk in chunks:
                documents.append(chunk.content)
                metadatas.append(chunk.metadata)
                ids.append(chunk.chunk_id)
            
            # Add to ChromaDB collection
            collection_name = self.chroma_client.default_collection_name
            collection = await self.chroma_client.get_or_create_collection(
                name=collection_name,
                embedding_function=None  # Use default embedding function
            )
            
            # Add documents in batches
            batch_size = 100
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i+batch_size]
                batch_meta = metadatas[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]
                
                collection.add(
                    documents=batch_docs,
                    metadatas=batch_meta,
                    ids=batch_ids
                )
                
            logger.info(f"Successfully embedded {len(documents)} Oracle chunks")
            
        except Exception as e:
            logger.error(f"Failed to embed Oracle chunks: {e}")
            raise
    
    async def _analyze_constraints(self, schema_name: str) -> Dict[str, int]:
        """Analyze database constraints as business rules."""
        logger.debug(f"Analyzing constraints for schema: {schema_name}")
        
        constraints = await self.oracle_client.get_constraints(schema_name)
        constraints_created = 0
        
        for constraint in constraints:
            try:
                # Create constraint node
                query = GraphQuery(
                    cypher="""
                    MERGE (con:OracleConstraint {schema_name: $schema_name, constraint_name: $constraint_name})
                    SET con.table_name = $table_name,
                        con.constraint_type = $constraint_type,
                        con.condition = $condition,
                        con.referenced_table = $referenced_table,
                        con.business_rule = $business_rule,
                        con.analyzed_at = datetime()
                    
                    WITH con
                    MATCH (t:OracleTable {schema_name: $schema_name, table_name: $table_name})
                    MERGE (t)-[:HAS_CONSTRAINT]->(con)
                    """,
                    parameters={
                        "schema_name": constraint.schema_name,
                        "constraint_name": constraint.constraint_name,
                        "table_name": constraint.table_name,
                        "constraint_type": constraint.constraint_type,
                        "condition": constraint.condition,
                        "referenced_table": constraint.referenced_table,
                        "business_rule": constraint.business_rule
                    },
                    read_only=False
                )
                
                await self.neo4j_client.execute_query(query)
                constraints_created += 1
                
                # Create business rule for CHECK constraints
                if constraint.constraint_type == 'C' and constraint.condition:
                    try:
                        rule_query = GraphQuery(
                            cypher="""
                            MERGE (br:BusinessRule {
                                source: 'oracle_constraint',
                                source_object: $source_object,
                                rule_text: $rule_text
                            })
                            SET br.domain = 'data_validation',
                                br.complexity = 'low',
                                br.rule_type = 'constraint',
                                br.analyzed_at = datetime()
                            
                            WITH br
                            MATCH (con:OracleConstraint {schema_name: $schema_name, constraint_name: $constraint_name})
                            MERGE (con)-[:ENFORCES_BUSINESS_RULE]->(br)
                            """,
                            parameters={
                                "source_object": f"{constraint.schema_name}.{constraint.table_name}.{constraint.constraint_name}",
                                "rule_text": constraint.condition,
                                "schema_name": constraint.schema_name,
                                "constraint_name": constraint.constraint_name
                            },
                            read_only=False
                        )
                        
                        await self.neo4j_client.execute_query(rule_query)
                        
                    except Exception as e:
                        logger.error(f"Failed to create business rule for constraint {constraint.constraint_name}: {e}")
                
            except Exception as e:
                logger.error(f"Failed to create constraint node for {constraint.constraint_name}: {e}")
        
        return {"constraints": constraints_created}
    
    async def _create_database_relationships(self, schema_name: str) -> Dict[str, int]:
        """Create relationships between database objects."""
        logger.debug(f"Creating database relationships for schema: {schema_name}")
        
        # Create foreign key relationships
        fk_query = GraphQuery(
            cypher="""
            MATCH (con:OracleConstraint {schema_name: $schema_name, constraint_type: 'R'})
            MATCH (source_table:OracleTable {schema_name: $schema_name, table_name: con.table_name})
            MATCH (target_table:OracleTable {schema_name: $schema_name, table_name: con.referenced_table})
            WHERE con.referenced_table IS NOT NULL
            MERGE (source_table)-[r:REFERENCES_TABLE]->(target_table)
            SET r.constraint_name = con.constraint_name,
                r.relationship_type = 'foreign_key'
            RETURN count(r) as relationships_created
            """,
            parameters={"schema_name": schema_name},
            read_only=False
        )
        
        result = await self.neo4j_client.execute_query(fk_query)
        relationships_created = 0
        
        if result.records:
            relationships_created = result.records[0].get("relationships_created", 0)
        
        return {"relationships": relationships_created}
    
    async def find_sql_queries_in_repository(self, repository_name: str) -> List[SQLQuery]:
        """
        Find SQL queries in repository code files.
        
        Args:
            repository_name: Name of repository to analyze
            
        Returns:
            List of SQL queries found in code
        """
        logger.info(f"Finding SQL queries in repository: {repository_name}")
        
        # Query Neo4j for Java files in the repository
        files_query = GraphQuery(
            cypher="""
            MATCH (repo:Repository {name: $repository_name})-[:CONTAINS]->(chunk:Chunk)
            WHERE chunk.file_path ENDS WITH '.java' 
               OR chunk.file_path ENDS WITH '.jsp'
            RETURN chunk.file_path, chunk.content, chunk.line_number
            """,
            parameters={"repository_name": repository_name},
            read_only=True
        )
        
        result = await self.neo4j_client.execute_query(files_query)
        sql_queries = []
        
        for record in result.records:
            file_path = record.get("chunk.file_path", "")
            content = record.get("chunk.content", "")
            line_number = record.get("chunk.line_number", 0)
            
            # Find SQL queries in content
            file_queries = self._extract_sql_from_content(
                repository_name, file_path, content, line_number
            )
            sql_queries.extend(file_queries)
        
        logger.info(f"Found {len(sql_queries)} SQL queries in {repository_name}")
        return sql_queries
    
    def _extract_sql_from_content(self, repository: str, file_path: str, 
                                content: str, start_line: int) -> List[SQLQuery]:
        """Extract SQL queries from file content."""
        queries = []
        
        for pattern in self.sql_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            
            for match in matches:
                sql_text = match.group(1).strip()
                
                # Skip trivial queries
                if len(sql_text) < 20 or not any(kw in sql_text.upper() for kw in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
                    continue
                
                # Determine query type
                query_type = self._determine_query_type(sql_text)
                
                # Extract table and column references
                tables = self._extract_table_references(sql_text)
                columns = self._extract_column_references(sql_text)
                
                # Estimate line number (rough approximation)
                line_number = start_line + content[:match.start()].count('\n')
                
                # Determine business context from file path and content
                business_context = self._determine_business_context(file_path, sql_text)
                
                query = SQLQuery(
                    repository=repository,
                    file_path=file_path,
                    line_number=line_number,
                    query_text=sql_text,
                    query_type=query_type,
                    tables_referenced=tables,
                    columns_referenced=columns,
                    business_context=business_context
                )
                
                queries.append(query)
        
        return queries
    
    def _determine_query_type(self, sql_text: str) -> str:
        """Determine SQL query type."""
        sql_upper = sql_text.upper().strip()
        
        if sql_upper.startswith('SELECT'):
            return 'SELECT'
        elif sql_upper.startswith('INSERT'):
            return 'INSERT'
        elif sql_upper.startswith('UPDATE'):
            return 'UPDATE'
        elif sql_upper.startswith('DELETE'):
            return 'DELETE'
        else:
            return 'OTHER'
    
    def _extract_table_references(self, sql_text: str) -> List[str]:
        """Extract table names from SQL query."""
        tables = []
        
        # Simple regex patterns for table extraction
        patterns = [
            r'FROM\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'JOIN\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'UPDATE\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'INTO\s+([A-Za-z_][A-Za-z0-9_]*)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql_text, re.IGNORECASE)
            tables.extend([match.upper() for match in matches])
        
        return list(set(tables))  # Remove duplicates
    
    def _extract_column_references(self, sql_text: str) -> List[str]:
        """Extract column names from SQL query (simplified)."""
        columns = []
        
        # Look for SELECT columns
        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_text, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            # Simple column extraction (doesn't handle complex expressions well)
            column_matches = re.findall(r'([A-Za-z_][A-Za-z0-9_]*)', select_clause)
            columns.extend([col.upper() for col in column_matches if col.upper() not in ['DISTINCT', 'AS']])
        
        # Look for WHERE clause columns
        where_matches = re.findall(r'WHERE.*?([A-Za-z_][A-Za-z0-9_]*)\s*[=<>!]', sql_text, re.IGNORECASE)
        columns.extend([col.upper() for col in where_matches])
        
        return list(set(columns))  # Remove duplicates
    
    def _determine_business_context(self, file_path: str, sql_text: str) -> str:
        """Determine business context from file path and SQL content."""
        file_lower = file_path.lower()
        sql_lower = sql_text.lower()
        
        # Context from file path
        if 'account' in file_lower:
            return 'account_management'
        elif 'customer' in file_lower:
            return 'customer_management'
        elif 'contract' in file_lower or 'policy' in file_lower:
            return 'contract_policy'
        elif 'payment' in file_lower or 'billing' in file_lower:
            return 'payment_billing'
        elif 'claim' in file_lower:
            return 'claims_processing'
        
        # Context from SQL content
        if any(table in sql_lower for table in ['account', 'customer', 'contract', 'policy']):
            return 'business_data_access'
        elif any(table in sql_lower for table in ['lookup', 'code', 'reference']):
            return 'reference_data_access'
        else:
            return 'general_data_access'
    
    async def create_code_to_database_mappings(self, repository_name: str) -> Dict[str, Any]:
        """
        Create mappings between application code and Oracle database objects.
        
        Args:
            repository_name: Repository to analyze
            
        Returns:
            Mapping results and statistics
        """
        logger.info(f"Creating code-to-database mappings for {repository_name}")
        
        if not ORACLE_AVAILABLE or not self.oracle_client.enabled:
            return {"status": "skipped", "reason": "Oracle not available"}
        
        try:
            # Find SQL queries in repository code
            sql_queries = await self.find_sql_queries_in_repository(repository_name)
            
            mappings_created = 0
            
            # Create relationships between code chunks and database objects
            for query in sql_queries:
                for table_name in query.tables_referenced:
                    try:
                        # Create relationship from code chunk to Oracle table
                        mapping_query = GraphQuery(
                            cypher="""
                            MATCH (chunk:Chunk {file_path: $file_path})
                            MATCH (table:OracleTable {table_name: $table_name})
                            MERGE (chunk)-[r:QUERIES_TABLE]->(table)
                            SET r.query_type = $query_type,
                                r.business_context = $business_context,
                                r.line_number = $line_number,
                                r.created_at = datetime()
                            """,
                            parameters={
                                "file_path": query.file_path,
                                "table_name": table_name,
                                "query_type": query.query_type,
                                "business_context": query.business_context,
                                "line_number": query.line_number
                            },
                            read_only=False
                        )
                        
                        await self.neo4j_client.execute_query(mapping_query)
                        mappings_created += 1
                        
                    except Exception as e:
                        logger.debug(f"Failed to create mapping for {query.file_path} -> {table_name}: {e}")
            
            return {
                "status": "completed",
                "repository": repository_name,
                "sql_queries_found": len(sql_queries),
                "mappings_created": mappings_created
            }
            
        except Exception as e:
            logger.error(f"Failed to create code-to-database mappings: {e}")
            return {"status": "error", "error": str(e)}


# Export main class
__all__ = ['OracleDatabaseAnalyzer', 'SQLQuery', 'DataFlowMapping']