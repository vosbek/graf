"""
Oracle Tool for Strands Chat Agent
==================================

Oracle database query tool that enables the chat agent to answer
questions about data sources, business rules in the database,
and data flow from UI components to Oracle tables.

This tool provides:
- Data source identification for UI fields
- Business rule discovery in PL/SQL procedures  
- Data lineage tracing from code to database
- Schema-aware query responses
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import re

logger = logging.getLogger(__name__)


class OracleTool:
    """
    Oracle database query tool for the chat agent.
    
    Enables the agent to answer "golden questions" about:
    - Where specific fields get their data from
    - What business rules govern data validation
    - How data flows from UI to database
    - What tables and columns contain specific business data
    """
    
    def __init__(self, oracle_client: Any):
        """
        Initialize Oracle tool with database client.
        
        Args:
            oracle_client: OracleDBClient instance
        """
        self._client = oracle_client
        
        # Common field name to column mappings
        self.field_mappings = {
            'specified_amount': ['SPECIFIED_AMOUNT', 'SPEC_AMT', 'AMOUNT_SPECIFIED'],
            'contract_type': ['CONTRACT_TYPE', 'CNTRCT_TYPE', 'TYPE_CODE'],
            'account_info': ['ACCOUNT_INFO', 'ACCT_INFO', 'ACCOUNT_DETAILS'],
            'customer_name': ['CUSTOMER_NAME', 'CUST_NAME', 'NAME'],
            'policy_number': ['POLICY_NUMBER', 'POLICY_NUM', 'PLCY_NUM'],
            'premium_amount': ['PREMIUM_AMOUNT', 'PREMIUM', 'PREM_AMT'],
            'effective_date': ['EFFECTIVE_DATE', 'EFF_DATE', 'START_DATE'],
            'status': ['STATUS', 'STATUS_CODE', 'STAT_CD']
        }
        
        # Business domain to table patterns
        self.domain_table_patterns = {
            'universal_life': ['%UNIVERSAL%', '%UL_%', '%LIFE%'],
            'account': ['%ACCOUNT%', '%ACCT%'],
            'contract': ['%CONTRACT%', '%CNTRCT%'],
            'customer': ['%CUSTOMER%', '%CUST%'],
            'policy': ['%POLICY%', '%PLCY%']
        }
    
    async def find_data_source(self, field_name: str, context: str = "") -> Dict[str, Any]:
        """
        Find Oracle table/column that provides data for a specific field.
        
        This is the core method for answering questions like:
        "Where does the 'Specified Amount' field get its data from?"
        
        Args:
            field_name: Field name to search for (e.g., "specified_amount")
            context: Business context (e.g., "Universal Life", "Account Info")
            
        Returns:
            Dictionary with data source information:
            {
                "field_name": "specified_amount",
                "data_sources": [
                    {
                        "table": "CONTRACT_DETAILS", 
                        "column": "SPECIFIED_AMOUNT",
                        "schema": "INSURANCE",
                        "business_purpose": "Stores contract coverage amount",
                        "data_type": "NUMBER(15,2)"
                    }
                ],
                "business_rules": [
                    "Amount must be greater than 0",
                    "Amount cannot exceed maximum coverage limit"
                ],
                "related_procedures": ["validate_contract_amount", "calculate_premium"],
                "confidence": 0.95
            }
        """
        if not self._client.enabled:
            return {
                "field_name": field_name,
                "data_sources": [],
                "business_rules": [],
                "related_procedures": [],
                "confidence": 0.0,
                "status": "oracle_disabled"
            }
        
        logger.debug(f"Finding data source for field: {field_name}, context: {context}")
        
        try:
            # 1. Get possible column name variations
            column_patterns = self._get_column_patterns(field_name)
            
            # 2. Search for matching columns across schemas
            data_sources = []
            
            for schema_name in self._client.schemas:
                for pattern in column_patterns:
                    columns = await self._client.find_columns_by_pattern(schema_name, pattern)
                    
                    for column in columns:
                        # Filter by context if provided
                        if context and not self._matches_context(column.table_name, context):
                            continue
                        
                        data_source = {
                            "table": column.table_name,
                            "column": column.column_name,
                            "schema": column.schema_name,
                            "business_purpose": column.comments or self._infer_business_purpose(column.column_name),
                            "data_type": column.data_type,
                            "nullable": column.nullable,
                            "table_context": self._classify_table_context(column.table_name)
                        }
                        
                        data_sources.append(data_source)
            
            # 3. Find related business rules
            business_rules = await self._find_related_business_rules(field_name, data_sources)
            
            # 4. Find related stored procedures
            related_procedures = await self._find_related_procedures(field_name, data_sources)
            
            # 5. Calculate confidence score
            confidence = self._calculate_confidence(field_name, data_sources, context)
            
            return {
                "field_name": field_name,
                "data_sources": data_sources[:5],  # Top 5 matches
                "business_rules": business_rules,
                "related_procedures": related_procedures,
                "confidence": confidence,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error finding data source for {field_name}: {e}")
            return {
                "field_name": field_name,
                "data_sources": [],
                "business_rules": [],
                "related_procedures": [],
                "confidence": 0.0,
                "status": "error",
                "error": str(e)
            }
    
    def _get_column_patterns(self, field_name: str) -> List[str]:
        """Get possible Oracle column name patterns for a field."""
        field_lower = field_name.lower().replace(' ', '_')
        
        # Check predefined mappings
        if field_lower in self.field_mappings:
            patterns = [f"%{col}%" for col in self.field_mappings[field_lower]]
        else:
            # Generate patterns from field name
            patterns = [
                f"%{field_lower.upper()}%",
                f"%{field_lower.replace('_', '')}%",
                f"%{field_lower.replace('_', '_')}%"
            ]
            
            # Add abbreviated patterns
            if '_' in field_lower:
                words = field_lower.split('_')
                abbreviated = ''.join(word[:3] for word in words)
                patterns.append(f"%{abbreviated.upper()}%")
        
        return patterns
    
    def _matches_context(self, table_name: str, context: str) -> bool:
        """Check if table name matches business context."""
        context_lower = context.lower()
        table_lower = table_name.lower()
        
        # Direct matching
        if any(word in table_lower for word in context_lower.split()):
            return True
        
        # Domain pattern matching
        for domain, patterns in self.domain_table_patterns.items():
            if domain in context_lower:
                for pattern in patterns:
                    if pattern.replace('%', '').lower() in table_lower:
                        return True
        
        return False
    
    def _classify_table_context(self, table_name: str) -> str:
        """Classify table business context."""
        table_upper = table_name.upper()
        
        if any(x in table_upper for x in ['ACCOUNT', 'ACCT']):
            return 'account_management'
        elif any(x in table_upper for x in ['CONTRACT', 'CNTRCT']):
            return 'contract_management'
        elif any(x in table_upper for x in ['CUSTOMER', 'CUST']):
            return 'customer_management'
        elif any(x in table_upper for x in ['POLICY', 'PLCY']):
            return 'policy_management'
        elif any(x in table_upper for x in ['LOOKUP', 'CODE', 'REF']):
            return 'reference_data'
        else:
            return 'business_data'
    
    def _infer_business_purpose(self, column_name: str) -> str:
        """Infer business purpose from column name."""
        col_upper = column_name.upper()
        
        if 'AMOUNT' in col_upper:
            return 'Monetary amount field'
        elif 'TYPE' in col_upper:
            return 'Classification/category field'
        elif 'STATUS' in col_upper:
            return 'Status indicator field'
        elif 'DATE' in col_upper:
            return 'Date/time field'
        elif col_upper.endswith('_ID') or col_upper.endswith('_NO'):
            return 'Identifier/reference field'
        elif 'NAME' in col_upper:
            return 'Name/description field'
        else:
            return 'Business data field'
    
    async def _find_related_business_rules(self, field_name: str, data_sources: List[Dict[str, Any]]) -> List[str]:
        """Find business rules related to a field."""
        business_rules = []
        
        try:
            # Search for check constraints on related columns
            for source in data_sources:
                constraints = await self._client.get_constraints(
                    source['schema'], 
                    source['table']
                )
                
                for constraint in constraints:
                    if (constraint.constraint_type == 'C' and 
                        constraint.condition and 
                        source['column'] in constraint.condition.upper()):
                        
                        rule = f"Database constraint: {constraint.condition}"
                        business_rules.append(rule)
            
            # Add common business rules based on field name
            field_lower = field_name.lower()
            if 'amount' in field_lower:
                business_rules.extend([
                    "Amount must be greater than 0",
                    "Amount format must be valid currency"
                ])
            elif 'date' in field_lower:
                business_rules.extend([
                    "Date must be valid calendar date",
                    "Date cannot be in the future (for some contexts)"
                ])
            elif 'status' in field_lower:
                business_rules.extend([
                    "Status must be valid code from lookup table",
                    "Status transitions must follow business rules"
                ])
                
        except Exception as e:
            logger.debug(f"Error finding business rules: {e}")
        
        return business_rules[:5]  # Top 5 rules
    
    async def _find_related_procedures(self, field_name: str, data_sources: List[Dict[str, Any]]) -> List[str]:
        """Find stored procedures related to a field."""
        procedures = []
        
        try:
            field_patterns = [
                field_name.lower(),
                field_name.lower().replace('_', ''),
                field_name.lower().replace(' ', '_')
            ]
            
            for source in data_sources:
                schema_procedures = await self._client.get_stored_procedures(source['schema'])
                
                for proc in schema_procedures:
                    proc_name_lower = proc.object_name.lower()
                    
                    # Check if procedure name contains field-related terms
                    if any(pattern in proc_name_lower for pattern in field_patterns):
                        procedures.append(f"{proc.schema_name}.{proc.object_name}")
                    
                    # Check if procedure source mentions the field or table
                    elif (source['column'].lower() in proc.source_code.lower() or 
                          source['table'].lower() in proc.source_code.lower()):
                        procedures.append(f"{proc.schema_name}.{proc.object_name}")
                        
        except Exception as e:
            logger.debug(f"Error finding related procedures: {e}")
        
        return procedures[:5]  # Top 5 procedures
    
    def _calculate_confidence(self, field_name: str, data_sources: List[Dict[str, Any]], context: str) -> float:
        """Calculate confidence score for data source matches."""
        if not data_sources:
            return 0.0
        
        total_score = 0.0
        max_score = 0.0
        
        for source in data_sources:
            score = 0.0
            
            # Exact column name match
            if field_name.lower().replace(' ', '_') == source['column'].lower():
                score += 0.4
            elif field_name.lower().replace(' ', '') in source['column'].lower():
                score += 0.3
            elif any(word in source['column'].lower() for word in field_name.lower().split()):
                score += 0.2
            
            # Context matching
            if context and self._matches_context(source['table'], context):
                score += 0.3
            
            # Business purpose relevance
            if source.get('business_purpose') and field_name.lower() in source['business_purpose'].lower():
                score += 0.2
            
            # Table context relevance
            if 'account' in field_name.lower() and source['table_context'] == 'account_management':
                score += 0.1
            
            max_score = max(max_score, score)
        
        return min(max_score, 1.0)
    
    async def trace_data_flow(self, jsp_field: str, repository: str) -> List[Dict[str, Any]]:
        """
        Trace data flow from JSP field back to Oracle source.
        
        Args:
            jsp_field: JSP form field name
            repository: Repository to analyze
            
        Returns:
            Data flow path: JSP → Action → DAO → SQL → Oracle Table/Column
        """
        if not self._client.enabled:
            return []
        
        logger.debug(f"Tracing data flow for JSP field: {jsp_field} in {repository}")
        
        try:
            # This would require integration with Neo4j to trace relationships
            # For now, return a simplified structure
            data_flow = []
            
            # Find potential data sources
            data_sources = await self.find_data_source(jsp_field)
            
            if data_sources['data_sources']:
                for source in data_sources['data_sources'][:3]:  # Top 3 matches
                    flow_item = {
                        "step": "database_source",
                        "type": "oracle_table",
                        "name": f"{source['schema']}.{source['table']}",
                        "column": source['column'],
                        "business_purpose": source['business_purpose'],
                        "confidence": data_sources['confidence']
                    }
                    data_flow.append(flow_item)
            
            return data_flow
            
        except Exception as e:
            logger.error(f"Error tracing data flow for {jsp_field}: {e}")
            return []
    
    async def get_business_domain_tables(self, domain: str) -> List[Dict[str, Any]]:
        """
        Get Oracle tables related to a specific business domain.
        
        Args:
            domain: Business domain (e.g., "account", "contract", "customer")
            
        Returns:
            List of tables in the business domain
        """
        if not self._client.enabled:
            return []
        
        domain_tables = []
        
        try:
            patterns = self.domain_table_patterns.get(domain.lower(), [f"%{domain.upper()}%"])
            
            for schema_name in self._client.schemas:
                for pattern in patterns:
                    tables = await self._client.find_tables_by_pattern(schema_name, pattern)
                    
                    for table in tables:
                        domain_tables.append({
                            "schema": table.schema_name,
                            "table": table.table_name,
                            "type": table.table_type,
                            "comments": table.comments,
                            "row_count": table.row_count,
                            "business_domain": domain
                        })
            
        except Exception as e:
            logger.error(f"Error getting domain tables for {domain}: {e}")
        
        return domain_tables
    
    async def validate_table_access(self, table_name: str, schema_name: str) -> bool:
        """
        Validate that we can access a specific Oracle table.
        
        Args:
            table_name: Oracle table name
            schema_name: Oracle schema name
            
        Returns:
            True if table is accessible, False otherwise
        """
        if not self._client.enabled:
            return False
        
        try:
            # Try to get table metadata
            tables = await self._client.get_table_schema(schema_name)
            return any(table.table_name.upper() == table_name.upper() for table in tables)
            
        except Exception as e:
            logger.debug(f"Error validating table access for {schema_name}.{table_name}: {e}")
            return False


# Export main class
__all__ = ['OracleTool']