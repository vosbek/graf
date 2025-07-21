# 🤖 AI Agent - Natural Language Interface

## 🎯 **Transform Technical Commands into Business Conversations**

The AI Agent eliminates the need for complex curl commands and technical interfaces. Instead, business users, project managers, and developers can ask questions in plain English and get intelligent, actionable answers.

---

## 🚀 **Getting Started**

### **Before: Technical Complexity**
```bash
# Old way - Technical curl commands
curl -X POST "http://localhost:8080/struts/analyze" \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/app", "repo_name": "legacy-app"}'

curl "http://localhost:8080/maven/conflicts?repository=legacy-app"

curl "http://localhost:8080/search/legacy-patterns?pattern=struts&limit=50"
```

### **After: Natural Conversations**
```python
# New way - Simple questions
agent.ask("What are the main features of this application?")
agent.ask("Show me all the payment processing endpoints")
agent.ask("How complex would it be to migrate the order management system?")
```

---

## 💬 **How to Use the AI Agent**

### **Method 1: Simple HTTP Requests (Python)**
```python
import requests

def ask_agent(question):
    response = requests.post("http://localhost:8080/agent/ask", 
                           json={"question": question})
    return response.json()["answer"]

# Ask any question about your codebase
answer = ask_agent("What are all the payment processing endpoints?")
print(answer)
```

### **Method 2: Using the Python Client**
```python
from mvp.example_usage import StrutsAnalysisClient

client = StrutsAnalysisClient()

# Ask questions directly
answer = client.ask("What features are in the user management section?")
print(answer)

# Filter by repository
answer = client.ask("Show me authentication logic", repository="user-service")
print(answer)
```

### **Method 3: Web Interface (FastAPI Docs)**
1. **Open**: http://localhost:8080/docs
2. **Navigate** to `/agent/ask` endpoint
3. **Click** "Try it out"
4. **Enter** your question in plain English
5. **Execute** and get intelligent responses

---

## 🎯 **What Questions Can You Ask?**

### **Application Overview**
```python
agent.ask("What are the main features of this application?")
agent.ask("How many web endpoints does this system have?")
agent.ask("What business domains are covered by this codebase?")
agent.ask("Give me a high-level overview of the application architecture")
```

### **Business Logic Discovery**
```python
agent.ask("Show me all the payment processing business logic")
agent.ask("What authentication methods are implemented?")
agent.ask("How does the order workflow function?")
agent.ask("What validation rules are enforced for user data?")
agent.ask("Where is the customer data handling logic?")
```

### **Migration Planning**
```python
agent.ask("How complex would it be to migrate this to GraphQL?")
agent.ask("What GraphQL types should I create for this application?")
agent.ask("Which features would be easiest to migrate first?")
agent.ask("What are the main technical dependencies I need to consider?")
agent.ask("Give me a step-by-step migration roadmap")
```

### **Security Analysis**
```python
agent.ask("What security measures are implemented in this application?")
agent.ask("How is user authentication handled?")
agent.ask("What input validation patterns are used?")
agent.ask("Are there any potential security vulnerabilities?")
agent.ask("How is sensitive data protected?")
```

### **Dependency Analysis**
```python
agent.ask("What repositories am I missing for complete development?")
agent.ask("Which components have the most dependencies?")
agent.ask("What external services does this application integrate with?")
agent.ask("How are database connections managed?")
agent.ask("What would break if I change the user service?")
```

---

## 🧠 **AI Agent Capabilities**

### **Available Tools**
The AI agent has access to 6 specialized tools:

| Tool | Purpose | Example Usage |
|------|---------|---------------|
| **get_struts_actions** | Find all web endpoints | "What features are available?" |
| **find_business_logic_for** | Search by business concept | "Show me payment logic" |
| **get_all_web_endpoints** | Complete API inventory | "List all URLs" |
| **analyze_feature_dependencies** | Impact analysis | "What depends on user management?" |
| **get_migration_suggestions** | GraphQL recommendations | "How to migrate to GraphQL?" |
| **search_for_security_patterns** | Security analysis | "What security is implemented?" |

### **Intelligent Responses**
The agent doesn't just return raw data - it provides:
- **Business-friendly explanations** without technical jargon
- **Contextual understanding** from the entire codebase
- **Actionable recommendations** for next steps
- **Complete analysis** across all repositories

---

## 📊 **Example Conversations**

### **Business Analysis Conversation**
```python
# Q: What are the main features of this application?
# A: "I found 5 major feature areas in your Struts application:
#    1. User Management - handles login, registration, and profiles
#    2. Product Catalog - manages inventory and product information  
#    3. Order Processing - handles cart, checkout, and order fulfillment
#    4. Payment Integration - processes credit cards and refunds
#    5. Admin Dashboard - provides reporting and system management
#    
#    Each area has multiple endpoints and substantial business logic."

# Q: How complex is the payment processing?
# A: "The payment processing is moderately complex with 4 main components:
#    - PaymentAction handles the main processing flow
#    - ValidationService ensures payment data integrity
#    - Integration with 2 external payment gateways
#    - Comprehensive error handling and retry logic
#    
#    For GraphQL migration, I'd recommend starting with read-only payment 
#    history queries before tackling the payment processing mutations."
```

### **Technical Deep-Dive Conversation**
```python
# Q: What security patterns need to be preserved during migration?
# A: "I identified several critical security patterns:
#    
#    Authentication:
#    - Custom session-based authentication in LoginAction
#    - Role-based access control with Admin/User/Guest roles
#    - Password encryption using MD5 (recommend upgrading to bcrypt)
#    
#    Input Validation:
#    - Struts validator framework for form validation
#    - SQL injection protection in DAO classes
#    - XSS protection in JSP pages
#    
#    For GraphQL migration, implement:
#    - JWT tokens for stateless authentication
#    - Input validation at resolver level
#    - Rate limiting for API endpoints"

# Q: Which repositories should I migrate first?
# A: "Based on dependency analysis, I recommend this migration order:
#    1. shared-models (no dependencies, used by others)
#    2. user-service (foundational, moderate complexity)
#    3. product-catalog (independent business logic)
#    4. order-service (depends on user and product services)
#    5. payment-service (highest complexity, depends on orders)
#    
#    This approach minimizes integration complexity and allows 
#    incremental testing at each stage."
```

---

## 🎯 **User-Specific Workflows**

### **For Project Managers**
```python
# Project assessment
questions = [
    "How many features does this application have?",
    "What would be the migration complexity?", 
    "Which business areas are most complex?",
    "What are the main technical risks?",
    "How long would migration typically take?"
]

for question in questions:
    answer = client.ask(question)
    print(f"Q: {question}")
    print(f"A: {answer}\n")
```

### **For Business Analysts**
```python
# Business process analysis
business_areas = [
    "user management",
    "payment processing", 
    "order management",
    "reporting and analytics",
    "customer support"
]

for area in business_areas:
    answer = client.ask(f"What business logic handles {area}?")
    print(f"=== {area.title()} ===")
    print(answer)
```

### **For Developers**
```python
# Technical implementation guidance
technical_questions = [
    "What are all the database dependencies?",
    "Which classes handle user authentication?",
    "What external services are integrated?",
    "How is error handling implemented?",
    "What patterns should I follow for new GraphQL resolvers?"
]

for question in technical_questions:
    answer = client.ask(question)
    # Use for implementation planning
```

---

## 🔧 **Advanced Usage**

### **Repository-Specific Analysis**
```python
# Focus on specific repositories
client.ask("Show me user authentication logic", repository="user-service")
client.ask("What payment methods are supported?", repository="payment-api")
client.ask("How are orders processed?", repository="order-management")
```

### **Contextual Follow-up Questions**
```python
# Build on previous answers
client.ask("What are the main payment endpoints?")
# Response identifies PaymentAction, RefundAction, ValidationAction

# Follow up with specific questions
client.ask("How does PaymentAction handle errors?")
client.ask("What external services does RefundAction call?")
client.ask("What validation rules does ValidationAction enforce?")
```

### **Integration Planning**
```python
# Plan system integration
client.ask("If I change the user authentication system, what else will be affected?")
client.ask("How do I integrate this payment system with a new GraphQL API?")
client.ask("What data needs to be migrated when moving to microservices?")
```

---

## 📈 **Agent Performance & Capabilities**

### **Response Times**
- **Simple queries**: 2-5 seconds
- **Complex analysis**: 5-15 seconds  
- **Cross-repository analysis**: 10-30 seconds

### **Accuracy**
- **Code discovery**: 95%+ comprehensive coverage
- **Business logic identification**: Highly accurate with context
- **Migration recommendations**: Based on industry best practices

### **Scalability**
- **Concurrent users**: Supports multiple simultaneous queries
- **Large codebases**: Optimized for enterprise-scale applications
- **Memory efficient**: Intelligent caching and query optimization

---

## 🛠️ **Agent Configuration**

### **Check Agent Health**
```python
# Verify agent is working
health = client.health_check()
print(health)
# {"status": "healthy", "agent_initialized": true, ...}
```

### **Get Agent Capabilities**
```python
# See what the agent can help with
capabilities = client.get_capabilities()
print(capabilities["example_questions"])
```

### **Monitor Agent Performance**
```bash
# Check agent endpoint status
curl http://localhost:8080/agent/health

# View system statistics
curl http://localhost:8080/status
```

---

## 🚨 **Troubleshooting**

### **Agent Not Responding**
```bash
# Check agent health
curl http://localhost:8080/agent/health

# Check system logs
podman logs codebase-rag-api | grep -i agent

# Restart if needed
podman restart codebase-rag-api
```

### **Slow Response Times**
```python
# Check if repositories are indexed
client.ask("How many repositories do you have indexed?")

# Verify system resources
curl http://localhost:8080/status
```

### **Unexpected Answers**
```python
# Verify data is properly indexed
client.ask("What files did you analyze for this repository?")

# Check for sufficient context
client.ask("How many code files are in the knowledge base?")
```

---

## 💡 **Best Practices**

### **Ask Clear, Specific Questions**
```python
# Good: Specific and actionable
"What validation rules are applied to user passwords?"

# Less effective: Too vague
"Tell me about security"
```

### **Use Business Language**
```python
# Good: Business-focused
"How does the order checkout process work?"

# Less effective: Too technical
"Show me all OrderAction class methods"
```

### **Build Context Progressively**
```python
# Start broad, then drill down
client.ask("What are the main payment features?")
# Then follow up with specifics
client.ask("How are credit card payments processed?")
client.ask("What happens when a payment fails?")
```

---

**The AI Agent transforms your complex Struts application into an approachable, conversational interface that anyone on your team can use to understand, analyze, and plan migration efforts.**

➡️ **Next**: [See complete dependency discovery workflow](dependency-discovery.md) or [Explore all features](../features.md)