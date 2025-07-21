"""
Business-friendly tools for Struts migration using Strand Agents SDK.
These tools provide natural language access to the knowledge graph.
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from strands import tool

logger = logging.getLogger(__name__)


class StrutsMigrationTools:
    """Collection of business-friendly tools for analyzing Struts codebases."""
    
    def __init__(self, neo4j_client, chromadb_client, search_client):
        """Initialize with existing database clients."""
        self.neo4j = neo4j_client
        self.chromadb = chromadb_client
        self.search = search_client
    
    @tool
    async def get_struts_actions(self, package_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find all Struts action classes (web endpoints) in the application.
        These represent the main features and pages users can access.
        You can optionally filter by Java package name like 'com.company.user' to focus on specific areas.
        Returns information about each action including the web URLs it handles.
        """
        try:
            # Use existing search to find Struts actions
            query = "extends Action execute method ActionForward"
            if package_filter:
                query += f" package {package_filter}"
            
            results = await self.search.search(
                query=query,
                limit=50,
                similarity_threshold=0.6
            )
            
            actions = []
            for result in results:
                if "Action" in result["file_path"] and ".java" in result["file_path"]:
                    class_name = Path(result["file_path"]).stem
                    actions.append({
                        "feature_name": class_name.replace("Action", ""),
                        "class_name": class_name,
                        "file_location": result["file_path"],
                        "relevance_score": result["score"],
                        "code_preview": result["content"][:300] + "..."
                    })
            
            return actions[:20]  # Limit for readability
            
        except Exception as e:
            logger.error(f"Error finding Struts actions: {e}")
            return [{"error": f"Could not retrieve actions: {str(e)}"}]
    
    @tool
    async def find_business_logic_for(self, business_concept: str) -> List[Dict[str, Any]]:
        """
        Search for code that implements specific business logic or handles business concepts.
        Use this to find how the application handles things like 'user authentication', 
        'payment processing', 'order management', 'data validation', etc.
        Returns code snippets and files where this business logic is implemented.
        """
        try:
            # Search for business logic using semantic search
            results = await self.search.search(
                query=f"{business_concept} business logic validation process method",
                limit=15,
                similarity_threshold=0.5
            )
            
            business_logic = []
            for result in results:
                business_logic.append({
                    "file_location": result["file_path"],
                    "business_concept": business_concept,
                    "relevance_score": result["score"],
                    "code_snippet": result["content"][:400] + "...",
                    "file_type": self._get_file_type(result["file_path"])
                })
            
            return business_logic
            
        except Exception as e:
            logger.error(f"Error finding business logic: {e}")
            return [{"error": f"Could not find business logic for '{business_concept}': {str(e)}"}]
    
    @tool
    async def get_all_web_endpoints(self, repository_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all web pages and API endpoints that users can access in the application.
        This helps understand the complete user interface and functionality available.
        Optionally filter by repository name if analyzing multiple applications.
        """
        try:
            # Search for action mappings and endpoints
            query = "action mapping path url endpoint struts-config"
            if repository_name:
                query += f" repository:{repository_name}"
            
            results = await self.search.search(
                query=query,
                limit=30,
                similarity_threshold=0.5
            )
            
            endpoints = []
            seen_endpoints = set()
            
            for result in results:
                # Extract potential URLs/paths from content
                content = result["content"]
                
                # Look for common URL patterns
                import re
                url_patterns = re.findall(r'["\']([/\w\-\.]+)["\']', content)
                
                for url in url_patterns:
                    if url.startswith('/') and url not in seen_endpoints and len(url) > 1:
                        seen_endpoints.add(url)
                        endpoints.append({
                            "endpoint_url": url,
                            "found_in_file": result["file_path"],
                            "context": content[:200] + "...",
                            "endpoint_type": self._classify_endpoint(url)
                        })
            
            return endpoints[:25]  # Limit for readability
            
        except Exception as e:
            logger.error(f"Error finding endpoints: {e}")
            return [{"error": f"Could not retrieve endpoints: {str(e)}"}]
    
    @tool
    async def analyze_feature_dependencies(self, feature_name: str) -> Dict[str, Any]:
        """
        Analyze what other parts of the system a specific feature depends on.
        Use this to understand the complexity of migrating or changing a feature.
        Provide the feature name like 'UserLogin', 'OrderProcessing', or 'PaymentHandling'.
        Returns dependencies, database tables used, external services called, etc.
        """
        try:
            # Search for the feature and its dependencies
            results = await self.search.search(
                query=f"{feature_name} class method dependency service DAO",
                limit=20,
                similarity_threshold=0.6
            )
            
            dependencies = {
                "feature_name": feature_name,
                "java_classes": [],
                "database_references": [],
                "external_services": [],
                "configuration_files": []
            }
            
            for result in results:
                file_path = result["file_path"]
                content = result["content"]
                
                # Categorize dependencies
                if ".java" in file_path:
                    dependencies["java_classes"].append({
                        "class_file": file_path,
                        "relevance": result["score"]
                    })
                elif any(ext in file_path for ext in [".xml", ".properties"]):
                    dependencies["configuration_files"].append({
                        "config_file": file_path,
                        "relevance": result["score"]
                    })
                
                # Look for database and service references in content
                import re
                if re.search(r'(SELECT|INSERT|UPDATE|DELETE|FROM)', content, re.IGNORECASE):
                    table_matches = re.findall(r'FROM\s+(\w+)', content, re.IGNORECASE)
                    dependencies["database_references"].extend(table_matches)
                
                if re.search(r'(service|client|api|http)', content, re.IGNORECASE):
                    dependencies["external_services"].append(f"Referenced in {Path(file_path).name}")
            
            # Remove duplicates and limit results
            dependencies["database_references"] = list(set(dependencies["database_references"]))[:10]
            dependencies["java_classes"] = dependencies["java_classes"][:10]
            dependencies["configuration_files"] = dependencies["configuration_files"][:5]
            
            return dependencies
            
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}")
            return {"error": f"Could not analyze dependencies for '{feature_name}': {str(e)}"}
    
    @tool
    async def get_migration_suggestions(self, repository_name: str) -> Dict[str, Any]:
        """
        Get AI-powered suggestions for migrating a Struts application to modern architecture.
        Analyzes the codebase and recommends GraphQL types, API operations, and migration strategies.
        Provide the repository name of the Struts application to analyze.
        """
        try:
            # Get business logic analysis
            business_results = await self.search.search(
                query=f"business logic validation calculate process transform repository:{repository_name}",
                limit=20,
                similarity_threshold=0.6
            )
            
            # Get data model analysis  
            data_results = await self.search.search(
                query=f"data model DTO bean entity form repository:{repository_name}",
                limit=15,
                similarity_threshold=0.6
            )
            
            # Generate suggestions based on findings
            suggestions = {
                "repository": repository_name,
                "analysis_summary": {
                    "business_logic_components": len(business_results),
                    "data_models_found": len(data_results)
                },
                "recommended_graphql_types": [],
                "recommended_queries": [],
                "recommended_mutations": [],
                "migration_priorities": [],
                "estimated_complexity": "Medium"
            }
            
            # Extract GraphQL type suggestions from data models
            for result in data_results[:8]:
                file_name = Path(result["file_path"]).stem
                if any(suffix in file_name for suffix in ["Form", "DTO", "Bean", "Data"]):
                    type_name = file_name.replace("Form", "").replace("DTO", "").replace("Bean", "").replace("Data", "")
                    if type_name and type_name not in suggestions["recommended_graphql_types"]:
                        suggestions["recommended_graphql_types"].append(type_name)
            
            # Suggest operations based on business logic
            for result in business_results[:10]:
                content = result["content"].lower()
                file_name = Path(result["file_path"]).stem
                
                if any(keyword in content for keyword in ["get", "find", "search", "list", "retrieve"]):
                    query_name = f"get{file_name.replace('Action', '').replace('Service', '')}"
                    if query_name not in suggestions["recommended_queries"]:
                        suggestions["recommended_queries"].append(query_name)
                        
                if any(keyword in content for keyword in ["save", "create", "update", "delete", "insert"]):
                    mutation_name = f"update{file_name.replace('Action', '').replace('Service', '')}"
                    if mutation_name not in suggestions["recommended_mutations"]:
                        suggestions["recommended_mutations"].append(mutation_name)
            
            # Add migration priorities
            suggestions["migration_priorities"] = [
                "Start with read-only operations (queries)",
                "Identify core business entities for GraphQL types",
                "Map Struts actions to GraphQL resolvers",
                "Preserve existing validation logic",
                "Test incrementally with parallel systems"
            ]
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating migration suggestions: {e}")
            return {"error": f"Could not generate suggestions for '{repository_name}': {str(e)}"}
    
    @tool
    async def search_for_security_patterns(self, repository_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find security-related code like authentication, authorization, input validation, and error handling.
        This helps identify security measures that need to be preserved during migration.
        Optionally specify repository name to focus the search.
        """
        try:
            security_patterns = [
                "authentication login security",
                "authorization permission role",
                "validation input sanitize",
                "error exception handling",
                "session management token"
            ]
            
            all_security_findings = []
            
            for pattern in security_patterns:
                query = pattern
                if repository_name:
                    query += f" repository:{repository_name}"
                
                results = await self.search.search(
                    query=query,
                    limit=8,
                    similarity_threshold=0.6
                )
                
                for result in results:
                    all_security_findings.append({
                        "security_pattern": pattern.split()[0],  # First word as category
                        "file_location": result["file_path"],
                        "relevance_score": result["score"],
                        "code_snippet": result["content"][:250] + "...",
                        "recommendation": self._get_security_recommendation(pattern)
                    })
            
            return all_security_findings[:20]  # Limit for readability
            
        except Exception as e:
            logger.error(f"Error finding security patterns: {e}")
            return [{"error": f"Could not analyze security patterns: {str(e)}"}]
    
    def _get_file_type(self, file_path: str) -> str:
        """Determine file type for categorization."""
        if file_path.endswith('.java'):
            return "Java Class"
        elif file_path.endswith('.jsp'):
            return "JSP Page"
        elif file_path.endswith('.xml'):
            return "Configuration"
        elif file_path.endswith('.properties'):
            return "Properties"
        else:
            return "Other"
    
    def _classify_endpoint(self, url: str) -> str:
        """Classify endpoint type based on URL pattern."""
        if '/api/' in url:
            return "API Endpoint"
        elif any(word in url.lower() for word in ['admin', 'manage']):
            return "Admin Interface"
        elif any(word in url.lower() for word in ['user', 'profile', 'account']):
            return "User Interface"
        else:
            return "Web Page"
    
    def _get_security_recommendation(self, pattern: str) -> str:
        """Get security migration recommendations."""
        recommendations = {
            "authentication": "Implement JWT or OAuth2 for stateless authentication",
            "authorization": "Use role-based access control (RBAC) in GraphQL",
            "validation": "Implement input validation at GraphQL resolver level",
            "error": "Use structured error handling with GraphQL error extensions",
            "session": "Consider stateless token-based session management"
        }
        
        for key, rec in recommendations.items():
            if key in pattern:
                return rec
        
        return "Review and adapt security pattern for modern architecture"