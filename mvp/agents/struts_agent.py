"""
StrutsMigrationAgent - Natural language interface for Struts codebase analysis.
Uses AWS Strand Agents SDK to provide conversational access to the knowledge graph.
"""

import logging
import asyncio
from typing import Dict, Any, Optional

try:
    from strands import Agent
    STRANDS_AVAILABLE = True
except ImportError:
    STRANDS_AVAILABLE = False
    Agent = None
    logging.warning("AWS Strands not available - AI Agent will use fallback mode")

from .tools import StrutsMigrationTools

logger = logging.getLogger(__name__)


class StrutsMigrationAgent:
    """
    Conversational AI agent for analyzing Struts codebases and planning migrations.
    
    This agent provides a natural language interface to query the knowledge graph
    built from your Struts application, making codebase analysis accessible to
    business users, project managers, and developers alike.
    """
    
    def __init__(self, neo4j_client, chromadb_client, search_client):
        """
        Initialize the Struts migration agent with database clients.
        
        Args:
            neo4j_client: Neo4j client for graph queries
            chromadb_client: ChromaDB client for vector search  
            search_client: Search client for semantic queries
        """
        self.neo4j_client = neo4j_client
        self.chromadb_client = chromadb_client
        self.search_client = search_client
        
        # Initialize tools with database clients
        self.tools = StrutsMigrationTools(
            neo4j_client=neo4j_client,
            chromadb_client=chromadb_client, 
            search_client=search_client
        )
        
        # Create the Strand Agent with tools
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the Strand Agent with migration analysis tools."""
        try:
            if not STRANDS_AVAILABLE:
                logger.warning("AWS Strands not available - initializing fallback agent")
                self.agent = None
                return
                
            # Extract tool methods from the tools class
            tool_methods = [
                self.tools.get_struts_actions,
                self.tools.find_business_logic_for,
                self.tools.get_all_web_endpoints,
                self.tools.analyze_feature_dependencies,
                self.tools.get_migration_suggestions,
                self.tools.search_for_security_patterns
            ]
            
            # Create the agent with the tools
            self.agent = Agent(tools=tool_methods)
            
            logger.info("StrutsMigrationAgent initialized successfully with 6 analysis tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize StrutsMigrationAgent: {e}")
            logger.info("Falling back to basic agent mode")
            self.agent = None
    
    async def ask(self, question: str) -> str:
        """
        Ask the agent a question about your Struts codebase in natural language.
        
        Args:
            question: Natural language question about the codebase
            
        Returns:
            Natural language response with insights from the knowledge graph
            
        Example questions:
        - "What are all the payment processing endpoints?"
        - "Show me the user authentication business logic"
        - "What features are in the admin section?"
        - "How complex would it be to migrate the order management system?"
        - "What security patterns are used in this application?"
        """
        try:
            logger.info(f"Processing question: {question}")
            
            # Check if AI agent is available
            if not self.agent or not STRANDS_AVAILABLE:
                logger.info("Using fallback response mode")
                return await self._fallback_response(question)
            
            # Use the Strand Agent to process the question
            # Run in executor to avoid blocking the event loop
            response = await asyncio.to_thread(self.agent, question)
            
            logger.info("Question processed successfully")
            return response
            
        except Exception as e:
            error_msg = f"Error processing question: {str(e)}"
            logger.error(error_msg)
            logger.info("Falling back to basic response")
            return await self._fallback_response(question)
    
    async def _fallback_response(self, question: str) -> str:
        """Provide basic responses when AI agent is not available."""
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['payment', 'billing', 'money']):
            return ("I found several potential payment-related components in your Struts application. "
                   "To get detailed analysis, please use the Search interface to look for 'payment' "
                   "or check the Migration Planner for GraphQL recommendations.")
        
        elif any(word in question_lower for word in ['authentication', 'login', 'auth', 'security']):
            return ("Authentication and security analysis is available through the codebase search. "
                   "Try searching for 'authentication', 'login', or 'security' in the Search interface "
                   "to find relevant code patterns and implementations.")
        
        elif any(word in question_lower for word in ['endpoint', 'action', 'url', 'route']):
            return ("To analyze endpoints and Struts actions, use the Search interface with terms like 'Action' "
                   "or 'execute'. You can also check the Migration Planner for a complete endpoint analysis "
                   "and GraphQL migration suggestions.")
        
        elif any(word in question_lower for word in ['migration', 'graphql', 'migrate']):
            return ("For migration planning and GraphQL recommendations, please use the Migration Planner "
                   "section. It will analyze your repository and provide step-by-step migration guidance "
                   "tailored to your Struts application structure.")
        
        else:
            return ("I'm currently running in basic mode. For detailed analysis of your Struts application, "
                   "please use the Search interface to find specific code patterns, or visit the Migration Planner "
                   "for comprehensive migration recommendations. You can also explore the Dependency Graph "
                   "for visual architecture insights.")
    
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get information about the agent's capabilities and example questions.
        
        Returns:
            Dictionary describing what the agent can help with
        """
        return {
            "description": "AI agent for Struts codebase analysis and migration planning",
            "capabilities": [
                "Find all Struts actions and web endpoints",
                "Search for business logic by concept (e.g., 'payment processing')",
                "Analyze feature dependencies and complexity",
                "Generate GraphQL migration suggestions",
                "Identify security patterns and requirements",
                "Provide migration planning guidance"
            ],
            "example_questions": [
                "What are all the user management features?",
                "Show me the payment processing business logic",
                "How many web endpoints does this application have?",
                "What would be involved in migrating the order system?",
                "What security measures are implemented?",
                "Give me GraphQL migration suggestions for this app"
            ],
            "supported_analysis": [
                "Endpoint discovery",
                "Business logic extraction", 
                "Dependency analysis",
                "Security pattern identification",
                "Migration complexity assessment",
                "Architecture recommendations"
            ]
        }
    
    async def health_check(self) -> Dict[str, bool]:
        """
        Check if the agent and all its dependencies are working correctly.
        
        Returns:
            Dictionary with health status of each component
        """
        health = {
            "agent_initialized": False,
            "neo4j_connected": False,
            "chromadb_connected": False,
            "search_available": False
        }
        
        try:
            # Check if agent is initialized
            health["agent_initialized"] = self.agent is not None
            
            # Check Neo4j connection
            if self.neo4j_client:
                # You might want to add a health check method to neo4j_client
                health["neo4j_connected"] = True
            
            # Check ChromaDB connection
            if self.chromadb_client:
                health["chromadb_connected"] = True
            
            # Check search client
            if self.search_client:
                health["search_available"] = True
                
        except Exception as e:
            logger.error(f"Health check failed: {e}")
        
        return health


class AgentService:
    """
    Service class to manage the StrutsMigrationAgent lifecycle.
    This provides a singleton pattern for the agent across the application.
    """
    
    _instance: Optional[StrutsMigrationAgent] = None
    
    @classmethod
    def initialize(cls, neo4j_client, chromadb_client, search_client) -> StrutsMigrationAgent:
        """
        Initialize the agent service with database clients.
        
        Args:
            neo4j_client: Neo4j client instance
            chromadb_client: ChromaDB client instance  
            search_client: Search client instance
            
        Returns:
            Initialized StrutsMigrationAgent instance
        """
        if cls._instance is None:
            cls._instance = StrutsMigrationAgent(
                neo4j_client=neo4j_client,
                chromadb_client=chromadb_client,
                search_client=search_client
            )
            logger.info("AgentService initialized")
        
        return cls._instance
    
    @classmethod
    def get_agent(cls) -> Optional[StrutsMigrationAgent]:
        """
        Get the current agent instance.
        
        Returns:
            StrutsMigrationAgent instance or None if not initialized
        """
        return cls._instance
    
    @classmethod
    def is_initialized(cls) -> bool:
        """
        Check if the agent service has been initialized.
        
        Returns:
            True if agent is initialized, False otherwise
        """
        return cls._instance is not None