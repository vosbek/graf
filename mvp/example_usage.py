"""
Example usage of the StrutsMigrationAgent for natural language codebase analysis.
This shows how to integrate with the AI agent for business-friendly queries.
"""

import asyncio
import requests
from typing import List, Dict, Any


class StrutsAnalysisClient:
    """
    Simple client for interacting with the StrutsMigrationAgent via HTTP API.
    This provides a Python interface for business users and developers.
    """
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def ask(self, question: str, repository: str = None) -> str:
        """
        Ask the AI agent a question about your Struts codebase.
        
        Args:
            question: Natural language question
            repository: Optional repository filter
            
        Returns:
            AI-generated answer
        """
        payload = {"question": question}
        if repository:
            payload["repository"] = repository
        
        response = self.session.post(
            f"{self.base_url}/agent/ask",
            json=payload
        )
        response.raise_for_status()
        return response.json()["answer"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get information about what the agent can help with."""
        response = self.session.get(f"{self.base_url}/agent/capabilities")
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> Dict[str, Any]:
        """Check if the agent is healthy and ready to answer questions."""
        response = self.session.get(f"{self.base_url}/agent/health")
        response.raise_for_status()
        return response.json()


def demonstrate_business_analysis():
    """
    Demonstrate how business users can analyze a Struts application
    without any technical knowledge of the underlying systems.
    """
    print("🤖 StrutsMigrationAgent - Business Analysis Demo")
    print("=" * 60)
    
    # Initialize the client
    client = StrutsAnalysisClient()
    
    # Check if agent is ready
    try:
        health = client.health_check()
        if health["status"] != "healthy":
            print("❌ Agent is not healthy. Please check the system.")
            return
        print("✅ AI Agent is ready!")
        print()
    except Exception as e:
        print(f"❌ Cannot connect to agent: {e}")
        return
    
    # Business analysis questions
    business_questions = [
        "What are the main features of this application?",
        "Show me all the payment processing endpoints",
        "What business logic handles user authentication?", 
        "How complex would it be to migrate the order management system?",
        "What security measures are implemented?",
        "Give me GraphQL migration suggestions for this application"
    ]
    
    print("🔍 Business Analysis Results:")
    print("-" * 40)
    
    for i, question in enumerate(business_questions, 1):
        print(f"\n{i}. Question: {question}")
        print("   " + "="*50)
        
        try:
            answer = client.ask(question)
            # Format the answer for better readability
            formatted_answer = "\n   ".join(answer.split("\n"))
            print(f"   Answer: {formatted_answer}")
            
        except Exception as e:
            print(f"   Error: {e}")
        
        print()


def demonstrate_migration_planning():
    """
    Show how to use the agent for systematic migration planning.
    """
    print("🚀 Migration Planning with AI Agent")
    print("=" * 50)
    
    client = StrutsAnalysisClient()
    
    # Migration planning workflow
    planning_steps = [
        {
            "phase": "Discovery",
            "questions": [
                "What are all the web endpoints in this application?",
                "How many Struts actions are there?",
                "What business domains are covered?"
            ]
        },
        {
            "phase": "Business Logic Analysis", 
            "questions": [
                "What business logic handles payments?",
                "Show me user management functionality",
                "What validation rules are implemented?"
            ]
        },
        {
            "phase": "Migration Strategy",
            "questions": [
                "What GraphQL types should I create?",
                "Which features would be easiest to migrate first?",
                "What are the main technical dependencies?"
            ]
        }
    ]
    
    for step in planning_steps:
        print(f"\n📋 Phase: {step['phase']}")
        print("-" * 30)
        
        for question in step['questions']:
            print(f"\nQ: {question}")
            try:
                answer = client.ask(question)
                # Truncate long answers for demo
                short_answer = answer[:200] + "..." if len(answer) > 200 else answer
                print(f"A: {short_answer}")
            except Exception as e:
                print(f"Error: {e}")


def demonstrate_technical_analysis():
    """
    Show how developers can get technical details for implementation.
    """
    print("🔧 Technical Analysis for Developers")
    print("=" * 45)
    
    client = StrutsAnalysisClient()
    
    # Technical questions developers might ask
    technical_queries = [
        "What security patterns need to be preserved during migration?",
        "Which components have the most dependencies?",
        "What database access patterns are used?",
        "How is error handling implemented across the application?",
        "What external service integrations exist?"
    ]
    
    for query in technical_queries:
        print(f"\n🔍 {query}")
        print("-" * len(query))
        
        try:
            answer = client.ask(query)
            # Extract key technical points
            if "found" in answer.lower():
                print(f"✅ {answer}")
            else:
                print(f"📝 {answer}")
                
        except Exception as e:
            print(f"❌ Error: {e}")


def demonstrate_comparison_with_curl():
    """
    Show the difference between using curl commands vs natural language.
    """
    print("⚖️  Comparison: curl vs Natural Language")
    print("=" * 50)
    
    comparisons = [
        {
            "goal": "Find Struts Actions",
            "old_way": "curl 'http://localhost:8080/struts/actions?repository=legacy-app'",
            "new_way": "What are all the user management features?",
            "benefit": "Business-friendly language, contextual understanding"
        },
        {
            "goal": "Search Business Logic", 
            "old_way": "curl 'http://localhost:8080/search/legacy-patterns?pattern=payment'",
            "new_way": "Show me all the payment processing business logic",
            "benefit": "Intelligent synthesis, actionable insights"
        },
        {
            "goal": "Migration Planning",
            "old_way": "curl 'http://localhost:8080/struts/migration-plan/legacy-app'", 
            "new_way": "How should I migrate this application to GraphQL?",
            "benefit": "Conversational guidance, step-by-step recommendations"
        }
    ]
    
    for comp in comparisons:
        print(f"\n🎯 Goal: {comp['goal']}")
        print(f"❌ Old Way: {comp['old_way']}")
        print(f"✅ New Way: {comp['new_way']}")
        print(f"💡 Benefit: {comp['benefit']}")
        print()


if __name__ == "__main__":
    """
    Run the demonstration examples.
    
    Prerequisites:
    1. Start the MVP: ./start-mvp-simple.sh
    2. Index your Struts application
    3. Run this script: python example_usage.py
    """
    
    print("🚀 StrutsMigrationAgent Demo")
    print("This demo shows how to use natural language instead of curl commands")
    print("=" * 70)
    
    try:
        # Run demonstrations
        demonstrate_comparison_with_curl()
        print("\n" + "="*70 + "\n")
        
        demonstrate_business_analysis()
        print("\n" + "="*70 + "\n")
        
        demonstrate_migration_planning()
        print("\n" + "="*70 + "\n") 
        
        demonstrate_technical_analysis()
        
        print("\n🎉 Demo Complete!")
        print("Your team can now analyze Struts applications using natural language!")
        
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("Make sure the MVP is running: ./start-mvp-simple.sh")