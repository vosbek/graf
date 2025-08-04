"""
Enhanced Neo4j schema for multi-repository enterprise analysis.
Supports cross-repository relationships, business flows, and enterprise-scale intelligence.
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Enhanced node types for multi-repository analysis."""
    # Repository-level nodes
    REPOSITORY = "Repository"
    REPOSITORY_GROUP = "RepositoryGroup"
    
    # Code structure nodes
    PACKAGE = "Package"
    FILE = "File"
    CLASS = "Class"
    METHOD = "Method"
    FIELD = "Field"
    INTERFACE = "Interface"
    
    # Business intelligence nodes
    BUSINESS_DOMAIN = "BusinessDomain"
    BUSINESS_OPERATION = "BusinessOperation"
    BUSINESS_FLOW = "BusinessFlow"
    API_ENDPOINT = "ApiEndpoint"
    DATABASE_OPERATION = "DatabaseOperation"
    VALIDATION_RULE = "ValidationRule"
    SECURITY_PATTERN = "SecurityPattern"
    INTEGRATION_POINT = "IntegrationPoint"
    
    # Configuration and infrastructure
    CONFIGURATION = "Configuration"
    DEPLOYMENT_UNIT = "DeploymentUnit"
    MESSAGE_QUEUE = "MessageQueue"
    
    # Maven and dependency nodes
    MAVEN_ARTIFACT = "MavenArtifact"
    DEPENDENCY = "Dependency"
    
    # Analysis and metadata nodes
    CODE_SMELL = "CodeSmell"
    VULNERABILITY = "Vulnerability"
    PERFORMANCE_HOTSPOT = "PerformanceHotspot"


class RelationshipType(Enum):
    """Enhanced relationship types for cross-repository analysis."""
    # Repository relationships
    DEPENDS_ON = "DEPENDS_ON"
    SHARES_ARTIFACT = "SHARES_ARTIFACT"
    COORDINATES_WITH = "COORDINATES_WITH"
    DEPLOYS_TOGETHER = "DEPLOYS_TOGETHER"
    
    # Code structure relationships
    CONTAINS = "CONTAINS"
    EXTENDS = "EXTENDS"
    IMPLEMENTS = "IMPLEMENTS"
    CALLS = "CALLS"
    ACCESSES = "ACCESSES"
    IMPORTS = "IMPORTS"
    OVERRIDES = "OVERRIDES"
    
    # Business intelligence relationships
    IMPLEMENTS_BUSINESS_RULE = "IMPLEMENTS_BUSINESS_RULE"
    PROCESSES = "PROCESSES"
    SPANS_REPOSITORIES = "SPANS_REPOSITORIES"
    PART_OF_FLOW = "PART_OF_FLOW"
    SECURED_BY = "SECURED_BY"
    VALIDATES_WITH = "VALIDATES_WITH"
    INTEGRATES_WITH = "INTEGRATES_WITH"
    
    # Data and execution relationships
    EXECUTES_SQL = "EXECUTES_SQL"
    READS_FROM = "READS_FROM"
    WRITES_TO = "WRITES_TO"
    PUBLISHES_TO = "PUBLISHES_TO"
    SUBSCRIBES_TO = "SUBSCRIBES_TO"
    
    # Analysis relationships
    HAS_VULNERABILITY = "HAS_VULNERABILITY"
    HAS_CODE_SMELL = "HAS_CODE_SMELL"
    PERFORMANCE_BOTTLENECK = "PERFORMANCE_BOTTLENECK"
    
    # Cross-repository relationships
    CROSS_REPO_CALL = "CROSS_REPO_CALL"
    SHARED_DATA_MODEL = "SHARED_DATA_MODEL"
    MIGRATION_DEPENDENCY = "MIGRATION_DEPENDENCY"


@dataclass
class RepositoryMetadata:
    """Metadata for repository nodes."""
    name: str
    url: str
    language: str
    framework: str
    business_domains: List[str]
    size_loc: int
    complexity_score: float
    last_modified: str
    team_owner: str
    deployment_environment: str
    
    # Multi-repo metadata
    depends_on_repos: List[str]
    provides_services: List[str]
    consumes_services: List[str]
    shared_artifacts: List[str]


@dataclass
class BusinessOperationMetadata:
    """Metadata for business operation nodes."""
    name: str
    operation_type: str  # payment, authentication, user_management, etc.
    business_domain: str
    customer_facing: bool
    financial_impact: str  # high, medium, low
    data_sensitivity: str  # pii, financial, public
    
    # Cross-repository metadata
    implementing_repositories: List[str]
    coordinating_operations: List[str]
    migration_complexity: int  # 1-10 scale
    migration_priority: str  # critical, high, medium, low


@dataclass
class BusinessFlowMetadata:
    """Metadata for business flow nodes spanning repositories."""
    name: str
    description: str
    flow_type: str  # user_journey, data_pipeline, integration_flow
    repositories_involved: List[str]
    
    # Business metadata
    business_value: str  # high, medium, low
    user_impact: str  # direct, indirect, none
    compliance_requirements: List[str]
    
    # Migration metadata
    migration_order: int  # sequencing for migration
    estimated_effort_weeks: int
    risk_level: str  # high, medium, low
    dependencies: List[str]  # other flows that must be migrated first


class MultiRepoSchemaManager:
    """Manager for multi-repository Neo4j schema operations."""
    
    def __init__(self):
        self.node_constraints = self._define_node_constraints()
        self.relationship_constraints = self._define_relationship_constraints()
        self.indexes = self._define_indexes()
        
    def _define_node_constraints(self) -> Dict[str, List[str]]:
        """Define unique constraints for node types."""
        return {
            NodeType.REPOSITORY.value: ["name"],
            NodeType.BUSINESS_DOMAIN.value: ["name"],
            NodeType.BUSINESS_OPERATION.value: ["name", "business_domain"],
            NodeType.BUSINESS_FLOW.value: ["name"],
            NodeType.API_ENDPOINT.value: ["url", "repository"],
            NodeType.METHOD.value: ["signature", "class", "repository"],
            NodeType.CLASS.value: ["name", "package", "repository"],
            NodeType.MAVEN_ARTIFACT.value: ["coordinates"],
            NodeType.INTEGRATION_POINT.value: ["name", "repository"]
        }
    
    def _define_relationship_constraints(self) -> Dict[str, Dict[str, Any]]:
        """Define relationship constraints and properties."""
        return {
            RelationshipType.DEPENDS_ON.value: {
                "properties": ["dependency_type", "strength", "criticality"],
                "allowed_nodes": [(NodeType.REPOSITORY, NodeType.REPOSITORY)]
            },
            RelationshipType.CROSS_REPO_CALL.value: {
                "properties": ["call_frequency", "data_size", "latency_sensitivity"],
                "allowed_nodes": [(NodeType.API_ENDPOINT, NodeType.API_ENDPOINT)]
            },
            RelationshipType.SPANS_REPOSITORIES.value: {
                "properties": ["flow_sequence", "coordination_type"],
                "allowed_nodes": [(NodeType.BUSINESS_FLOW, NodeType.REPOSITORY)]
            },
            RelationshipType.IMPLEMENTS_BUSINESS_RULE.value: {
                "properties": ["implementation_completeness", "business_criticality"],
                "allowed_nodes": [(NodeType.METHOD, NodeType.BUSINESS_OPERATION)]
            }
        }
    
    def _define_indexes(self) -> Dict[str, List[str]]:
        """Define indexes for performance optimization."""
        return {
            # Repository-level indexes
            NodeType.REPOSITORY.value: ["name", "business_domains", "framework"],
            NodeType.REPOSITORY_GROUP.value: ["name", "group_type"],
            
            # Business intelligence indexes
            NodeType.BUSINESS_DOMAIN.value: ["name"],
            NodeType.BUSINESS_OPERATION.value: ["operation_type", "business_domain", "customer_facing"],
            NodeType.BUSINESS_FLOW.value: ["flow_type", "repositories_involved"],
            NodeType.API_ENDPOINT.value: ["repository", "endpoint_type", "business_domain"],
            
            # Code structure indexes
            NodeType.METHOD.value: ["repository", "class", "business_domain"],
            NodeType.CLASS.value: ["repository", "package", "business_domain"],
            
            # Cross-repository analysis indexes
            NodeType.INTEGRATION_POINT.value: ["repository", "integration_type"],
            NodeType.SECURITY_PATTERN.value: ["pattern_type", "repository"]
        }
    
    def generate_schema_cypher(self) -> List[str]:
        """Generate Cypher statements to create the enhanced schema."""
        cypher_statements = []
        
        # Create constraints
        for node_type, properties in self.node_constraints.items():
            for prop in properties:
                cypher_statements.append(
                    f"CREATE CONSTRAINT {node_type.lower()}_{prop}_unique IF NOT EXISTS "
                    f"FOR (n:{node_type}) REQUIRE n.{prop} IS UNIQUE"
                )
        
        # Create indexes
        for node_type, properties in self.indexes.items():
            for prop in properties:
                cypher_statements.append(
                    f"CREATE INDEX {node_type.lower()}_{prop}_index IF NOT EXISTS "
                    f"FOR (n:{node_type}) ON (n.{prop})"
                )
        
        # Create composite indexes for cross-repository queries
        cypher_statements.extend([
            # Repository + business domain composite index
            "CREATE INDEX repo_domain_composite IF NOT EXISTS "
            "FOR (r:Repository) ON (r.name, r.business_domains)",
            
            # Method + repository + business domain composite index
            "CREATE INDEX method_repo_domain_composite IF NOT EXISTS "
            "FOR (m:Method) ON (m.repository, m.business_domain, m.class)",
            
            # Business flow + repositories composite index
            "CREATE INDEX flow_repos_composite IF NOT EXISTS "
            "FOR (f:BusinessFlow) ON (f.repositories_involved, f.flow_type)",
            
            # Cross-repository relationship index
            "CREATE INDEX cross_repo_calls IF NOT EXISTS "
            "FOR ()-[r:CROSS_REPO_CALL]-() ON (r.source_repository, r.target_repository)"
        ])
        
        return cypher_statements
    
    def create_repository_node_cypher(self, metadata: RepositoryMetadata) -> str:
        """Generate Cypher to create a repository node with enhanced metadata."""
        return f"""
        MERGE (r:Repository {{name: $name}})
        SET r.url = $url,
            r.language = $language,
            r.framework = $framework,
            r.business_domains = $business_domains,
            r.size_loc = $size_loc,
            r.complexity_score = $complexity_score,
            r.last_modified = $last_modified,
            r.team_owner = $team_owner,
            r.deployment_environment = $deployment_environment,
            r.depends_on_repos = $depends_on_repos,
            r.provides_services = $provides_services,
            r.consumes_services = $consumes_services,
            r.shared_artifacts = $shared_artifacts,
            r.created_at = datetime(),
            r.updated_at = datetime()
        RETURN r
        """
    
    def create_business_operation_cypher(self, metadata: BusinessOperationMetadata) -> str:
        """Generate Cypher to create a business operation node."""
        return f"""
        MERGE (op:BusinessOperation {{name: $name, business_domain: $business_domain}})
        SET op.operation_type = $operation_type,
            op.customer_facing = $customer_facing,
            op.financial_impact = $financial_impact,
            op.data_sensitivity = $data_sensitivity,
            op.implementing_repositories = $implementing_repositories,
            op.coordinating_operations = $coordinating_operations,
            op.migration_complexity = $migration_complexity,
            op.migration_priority = $migration_priority,
            op.created_at = datetime(),
            op.updated_at = datetime()
        
        // Link to business domain
        MERGE (domain:BusinessDomain {{name: $business_domain}})
        MERGE (domain)-[:CONTAINS]->(op)
        
        // Link to implementing repositories
        UNWIND $implementing_repositories AS repo_name
        MERGE (repo:Repository {{name: repo_name}})
        MERGE (repo)-[:IMPLEMENTS]->(op)
        
        RETURN op
        """
    
    def create_business_flow_cypher(self, metadata: BusinessFlowMetadata) -> str:
        """Generate Cypher to create a business flow spanning repositories."""
        return f"""
        MERGE (flow:BusinessFlow {{name: $name}})
        SET flow.description = $description,
            flow.flow_type = $flow_type,
            flow.repositories_involved = $repositories_involved,
            flow.business_value = $business_value,
            flow.user_impact = $user_impact,
            flow.compliance_requirements = $compliance_requirements,
            flow.migration_order = $migration_order,
            flow.estimated_effort_weeks = $estimated_effort_weeks,
            flow.risk_level = $risk_level,
            flow.dependencies = $dependencies,
            flow.created_at = datetime(),
            flow.updated_at = datetime()
        
        // Link to involved repositories
        UNWIND $repositories_involved AS repo_name
        MERGE (repo:Repository {{name: repo_name}})
        MERGE (flow)-[:SPANS_REPOSITORIES]->(repo)
        
        // Link flow dependencies
        UNWIND $dependencies AS dep_flow_name
        MERGE (dep_flow:BusinessFlow {{name: dep_flow_name}})
        MERGE (dep_flow)-[:PREREQUISITE_FOR]->(flow)
        
        RETURN flow
        """
    
    def create_cross_repo_relationship_cypher(self, 
                                            source_repo: str, 
                                            target_repo: str,
                                            relationship_type: RelationshipType,
                                            properties: Dict[str, Any]) -> str:
        """Generate Cypher to create cross-repository relationships."""
        prop_assignments = ", ".join([f"r.{key} = ${key}" for key in properties.keys()])
        
        return f"""
        MATCH (source:Repository {{name: $source_repo}})
        MATCH (target:Repository {{name: $target_repo}})
        MERGE (source)-[r:{relationship_type.value}]->(target)
        SET {prop_assignments},
            r.created_at = datetime(),
            r.updated_at = datetime()
        RETURN r
        """
    
    def get_cross_repo_analysis_queries(self) -> Dict[str, str]:
        """Get predefined queries for cross-repository analysis."""
        return {
            "find_business_flows_for_repos": """
                MATCH (flow:BusinessFlow)-[:SPANS_REPOSITORIES]->(repo:Repository)
                WHERE repo.name IN $repository_names
                RETURN flow, COLLECT(repo.name) as involved_repositories
                ORDER BY flow.business_value DESC, flow.migration_order ASC
            """,
            
            "find_cross_repo_dependencies": """
                MATCH (source:Repository)-[r:DEPENDS_ON]->(target:Repository)
                WHERE source.name IN $repository_names OR target.name IN $repository_names
                RETURN source.name, target.name, r.dependency_type, r.strength, r.criticality
                ORDER BY r.criticality DESC
            """,
            
            "find_shared_business_operations": """
                MATCH (op:BusinessOperation)<-[:IMPLEMENTS]-(repo:Repository)
                WHERE repo.name IN $repository_names
                WITH op, COLLECT(repo.name) as implementing_repos
                WHERE size(implementing_repos) > 1
                RETURN op.name, op.business_domain, implementing_repos, op.migration_complexity
                ORDER BY op.migration_complexity DESC
            """,
            
            "analyze_migration_impact": """
                MATCH (component)-[:PART_OF_FLOW]->(flow:BusinessFlow)
                WHERE component.repository IN $repository_names
                MATCH (flow)-[:SPANS_REPOSITORIES]->(affected_repo:Repository)
                RETURN flow.name, 
                       COLLECT(DISTINCT affected_repo.name) as affected_repositories,
                       flow.estimated_effort_weeks,
                       flow.risk_level,
                       COUNT(component) as affected_components
                ORDER BY flow.estimated_effort_weeks DESC
            """,
            
            "find_integration_points": """
                MATCH (integration:IntegrationPoint)-[:INTEGRATES_WITH]->(external)
                WHERE integration.repository IN $repository_names
                RETURN integration.name, 
                       integration.repository, 
                       integration.integration_type,
                       external.name as external_system,
                       integration.data_sensitivity
                ORDER BY integration.data_sensitivity DESC
            """
        }


# Schema validation and migration utilities
class SchemaValidator:
    """Validates multi-repository schema consistency."""
    
    @staticmethod
    def validate_repository_metadata(metadata: RepositoryMetadata) -> List[str]:
        """Validate repository metadata for consistency."""
        errors = []
        
        if not metadata.name:
            errors.append("Repository name is required")
        
        if not metadata.business_domains:
            errors.append("At least one business domain must be specified")
        
        if metadata.complexity_score < 0 or metadata.complexity_score > 10:
            errors.append("Complexity score must be between 0 and 10")
        
        return errors
    
    @staticmethod
    def validate_business_flow_metadata(metadata: BusinessFlowMetadata) -> List[str]:
        """Validate business flow metadata for consistency."""
        errors = []
        
        if not metadata.repositories_involved:
            errors.append("Business flow must involve at least one repository")
        
        if len(metadata.repositories_involved) < 2:
            errors.append("Cross-repository business flow should involve multiple repositories")
        
        if metadata.estimated_effort_weeks <= 0:
            errors.append("Estimated effort must be positive")
        
        return errors


# Usage example and schema initialization
def initialize_multi_repo_schema(neo4j_client) -> bool:
    """Initialize the multi-repository schema in Neo4j."""
    try:
        schema_manager = MultiRepoSchemaManager()
        cypher_statements = schema_manager.generate_schema_cypher()
        
        for statement in cypher_statements:
            neo4j_client.run(statement)
            logger.info(f"Executed schema statement: {statement}")
        
        logger.info("Multi-repository schema initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize multi-repository schema: {e}")
        return False


# Export key classes and functions
__all__ = [
    'NodeType', 'RelationshipType', 'RepositoryMetadata', 'BusinessOperationMetadata',
    'BusinessFlowMetadata', 'MultiRepoSchemaManager', 'SchemaValidator',
    'initialize_multi_repo_schema'
]