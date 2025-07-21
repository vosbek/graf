#!/bin/bash

# =============================================================================
# ENVIRONMENT CHECK SCRIPT
# =============================================================================
# Quick verification that environment is properly configured

echo "🔍 Checking MVP Environment Configuration..."
echo

# =============================================================================
# CONFIGURATION FILES
# =============================================================================

echo "📁 Configuration Files:"

if [ -f ".env" ]; then
    echo "✅ .env file exists"
    
    # Check for key settings
    if grep -q "CHROMA_HOST" .env; then
        echo "✅ ChromaDB configuration found"
    fi
    
    if grep -q "NEO4J_URI" .env; then
        echo "✅ Neo4j configuration found"
    fi
    
    if grep -q "AWS_ACCESS_KEY_ID" .env && [ -n "$(grep AWS_ACCESS_KEY_ID .env | cut -d'=' -f2)" ]; then
        echo "✅ AWS credentials configured"
    else
        echo "⚠️  AWS credentials not configured (AI Agent will use fallback mode)"
    fi
    
else
    echo "❌ .env file missing - using defaults"
fi

if [ -f ".env.template" ]; then
    echo "✅ .env.template available for customization"
fi

if [ -f ".aws-credentials.template" ]; then
    echo "✅ AWS credentials template available"
fi

echo

# =============================================================================
# REQUIRED DIRECTORIES
# =============================================================================

echo "📂 Required Directories:"

REPOS_PATH="${REPOS_PATH:-./data/repositories}"
if [ -d "$REPOS_PATH" ]; then
    echo "✅ Repository storage: $REPOS_PATH"
else
    echo "⚠️  Repository storage missing: $REPOS_PATH (will be created on startup)"
fi

if [ -d "logs" ]; then
    echo "✅ Logs directory exists"
else
    echo "⚠️  Logs directory missing (will be created on startup)"
fi

if [ -d "frontend/build" ]; then
    echo "✅ Frontend build exists"
else
    echo "❌ Frontend not built (run: ./start-mvp-with-ui.sh)"
fi

echo

# =============================================================================
# SYSTEM REQUIREMENTS
# =============================================================================

echo "🖥️  System Requirements:"

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    echo "✅ Python: $PYTHON_VERSION"
else
    echo "❌ Python 3 not found"
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✅ Node.js: $NODE_VERSION"
else
    echo "❌ Node.js not found"
fi

# Check npm
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo "✅ npm: $NPM_VERSION"
else
    echo "❌ npm not found"
fi

# Check Git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | cut -d' ' -f3)
    echo "✅ Git: $GIT_VERSION"
else
    echo "❌ Git not found"
fi

# Check available memory
if command -v free &> /dev/null; then
    MEMORY_GB=$(free -h | awk '/^Mem:/ {print $2}')
    echo "✅ Available Memory: $MEMORY_GB"
elif command -v vm_stat &> /dev/null; then
    # macOS
    echo "✅ Memory: Available (macOS detected)"
else
    echo "⚠️  Memory info not available"
fi

echo

# =============================================================================
# NETWORK CONNECTIVITY
# =============================================================================

echo "🌐 Network Connectivity:"

# Check local ports
if command -v netstat &> /dev/null; then
    if netstat -an | grep -q ":8080"; then
        echo "⚠️  Port 8080 already in use"
    else
        echo "✅ Port 8080 available"
    fi
    
    if netstat -an | grep -q ":8000"; then
        echo "⚠️  Port 8000 already in use"
    else
        echo "✅ Port 8000 available"
    fi
else
    echo "⚠️  Cannot check port availability"
fi

echo

# =============================================================================
# AWS CONFIGURATION (OPTIONAL)
# =============================================================================

echo "☁️  AWS Configuration (Optional):"

if [ -n "$AWS_ACCESS_KEY_ID" ]; then
    echo "✅ AWS_ACCESS_KEY_ID set in environment"
elif grep -q "AWS_ACCESS_KEY_ID=" .env 2>/dev/null && [ -n "$(grep AWS_ACCESS_KEY_ID .env | cut -d'=' -f2)" ]; then
    echo "✅ AWS_ACCESS_KEY_ID set in .env"
else
    echo "⚠️  AWS credentials not configured"
fi

if command -v aws &> /dev/null; then
    echo "✅ AWS CLI installed"
    
    # Test AWS access
    if aws sts get-caller-identity &> /dev/null; then
        echo "✅ AWS credentials valid"
    else
        echo "⚠️  AWS credentials invalid or not configured"
    fi
else
    echo "⚠️  AWS CLI not installed"
fi

echo

# =============================================================================
# SUMMARY AND RECOMMENDATIONS
# =============================================================================

echo "📋 Summary:"
echo

echo "Required for MVP:"
echo "  ✅ Python 3.8+"
echo "  ✅ Node.js 14+"
echo "  ✅ Git"
echo "  ✅ 4GB+ RAM"

echo
echo "Optional for full functionality:"
echo "  ⚠️  AWS credentials (for full AI Agent)"
echo "  ⚠️  Docker (for containerized setup)"

echo
echo "🚀 Next Steps:"

if [ ! -f ".env" ]; then
    echo "  1. Create .env file: cp .env.template .env"
fi

# Check AWS credential configuration more thoroughly
echo
echo "🔐 AWS Configuration Status:"

# Check if any AWS credentials are configured
AWS_CONFIGURED=false

if [ -n "$AWS_ACCESS_KEY_ID" ] && [ -n "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "✅ AWS credentials set via environment variables"
    AWS_CONFIGURED=true
elif grep -q "AWS_ACCESS_KEY_ID=" .env 2>/dev/null && [ -n "$(grep AWS_ACCESS_KEY_ID .env | cut -d'=' -f2)" ]; then
    echo "✅ AWS credentials configured in .env file"
    AWS_CONFIGURED=true
elif [ -f "$HOME/.aws/credentials" ]; then
    echo "✅ AWS credentials file exists: $HOME/.aws/credentials"
    AWS_CONFIGURED=true
elif [ -f "$HOME/.aws/config" ]; then
    echo "⚠️  AWS config exists but no credentials file found"
else
    echo "❌ No AWS credentials found"
fi

if [ "$AWS_CONFIGURED" = true ]; then
    echo "   Mode: FULL AI Agent with AWS Strands support"
    echo "   Capabilities: Natural language analysis, advanced migration planning"
else
    echo "   Mode: FALLBACK Agent (basic responses only)"
    echo "   Setup: See .aws-credentials.template for AWS configuration"
fi

echo
if [ ! -d "frontend/build" ]; then
    echo "  2. Build and start MVP: ./start-mvp-with-ui.sh"
else
    echo "  2. Start MVP: ./start-mvp-with-ui.sh"
fi

echo "  3. Open browser: http://localhost:8080"
echo "  4. Check status: curl http://localhost:8080/health"
echo "  5. Index your first repository"
echo "  6. Start analyzing!"

echo
echo "📋 Startup Validation:"
echo "   - MVP will validate AWS credentials on startup"
echo "   - Check logs for detailed credential status"
echo "   - Visit /health endpoint for real-time status"
echo
echo "For AWS setup: See .aws-credentials.template"
echo "For troubleshooting: See SETUP-GUIDE.md"