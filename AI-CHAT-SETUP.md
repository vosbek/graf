# 🤖 AI Chat Setup Guide

## Overview

The AI Chat feature uses the **Strands Agent** architecture with AWS Bedrock for LLM inference. It provides intelligent responses about your codebase by combining:

- **ChromaDB** semantic search for relevant code chunks
- **Neo4j** graph traversal for code relationships 
- **AWS Bedrock** (Claude) for natural language generation

## Prerequisites

- ✅ **System running** (containers + API server)
- ✅ **Repositories indexed** in ChromaDB and Neo4j
- ❌ **AWS Bedrock credentials** (required for AI Chat)

## Configuration

### Step 1: AWS Bedrock Access

You need AWS credentials with Bedrock access. Choose ONE of these approaches:

#### Option A: AWS CLI Profile (Recommended)
```bash
# Install AWS CLI and configure
aws configure --profile your-profile-name
# Enter your AWS Access Key ID, Secret, and Region
```

#### Option B: Environment Variables
```bash
# Set these in your environment
export AWS_ACCESS_KEY_ID="your_access_key_here"
export AWS_SECRET_ACCESS_KEY="your_secret_key_here"
export AWS_REGION="us-east-1"
```

### Step 2: Update .env File

Add these settings to your `.env` file:

```env
# AWS Bedrock Configuration (REQUIRED)
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
AWS_REGION=us-east-1

# Choose ONE credential approach:

# Option A: Use AWS Profile
AWS_PROFILE=your-profile-name

# Option B: Direct credentials  
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here

# Optional: LLM Parameters (defaults shown)
LLM_MAX_INPUT_TOKENS=8000
LLM_MAX_OUTPUT_TOKENS=1024
LLM_REQUEST_TIMEOUT_SECONDS=30.0
```

### Step 3: Restart API Server

After updating `.env`, restart the API server:

```powershell
# Stop current server (Ctrl+C if running in terminal)
# Then restart
.\START.ps1 -Mode api
```

## Verification

### Check AI Chat Status

1. **API Logs**: Look for these messages in startup logs:
   ```
   Chat feature enabled (Bedrock config validated)
   Chat router registered
   ```

2. **Health Endpoint**: Check if chat is enabled:
   ```bash
   curl http://localhost:8081/api/v1/health/ready
   ```

3. **Frontend**: The AI Chat page should show:
   - ✅ System ready (green)
   - ✅ Input field enabled
   - ✅ Send button clickable

### Test AI Chat

1. **Navigate** to http://localhost:3000/chat
2. **Ask a question** like:
   - "What repositories do we have?"
   - "Show me the main services"
   - "What are the key dependencies?"
3. **Expect response** with:
   - Relevant answer about your codebase
   - Citation count (e.g., "3 citations")

## Troubleshooting

### "Chat router not registered (chat_enabled is False)"

**Cause**: Bedrock configuration validation failed

**Solutions**:
1. Check your AWS credentials are valid
2. Ensure `BEDROCK_MODEL_ID` and `AWS_REGION` are set
3. Verify AWS account has Bedrock access
4. Test AWS connection: `aws bedrock list-foundation-models --region us-east-1`

### "Bedrock provider invalid" Error

**Cause**: AWS credentials or permissions issue

**Solutions**:
1. Verify IAM permissions include `bedrock:InvokeModel`
2. Check if Claude model is available in your region
3. Try different model ID: `anthropic.claude-3-haiku-20240307-v1:0`

### "Chat components unavailable" Error

**Cause**: Strands agent modules not found

**Solutions**:
1. Check that `strands/` directory exists in project
2. Verify Python imports work: `python -c "from strands.agents.chat_agent import ChatAgent"`

### Frontend Shows "System is not ready"

**Cause**: Backend not healthy or chat not enabled

**Solutions**:
1. Check backend is running: `curl http://localhost:8081/api/v1/health/`
2. Verify containers are healthy: `podman ps` or `docker ps`
3. Check API logs for errors

## AWS Bedrock Models

### Recommended Models

| Model ID | Description | Use Case |
|----------|-------------|----------|
| `anthropic.claude-3-5-sonnet-20241022-v2:0` | Latest Claude 3.5 Sonnet | Best balance of speed/quality |
| `anthropic.claude-3-haiku-20240307-v1:0` | Claude 3 Haiku | Faster, lower cost |
| `anthropic.claude-3-opus-20240229-v1:0` | Claude 3 Opus | Highest quality |

### Available Regions

- `us-east-1` (N. Virginia) - Most models available
- `us-west-2` (Oregon) - Good alternative  
- `eu-west-1` (Ireland) - European users

## Cost Considerations

**Typical Usage**:
- Input: ~2000-4000 tokens per query (code context + question)
- Output: ~200-500 tokens per response
- **Claude 3.5 Sonnet**: ~$0.01-0.02 per query
- **Claude 3 Haiku**: ~$0.001-0.002 per query

**Monthly Estimate** (100 queries):
- Sonnet: ~$1-2/month
- Haiku: ~$0.10-0.20/month

## Architecture Details

### Query Flow

```
User Question
    ↓
ChatInterface.js (Frontend)
    ↓
POST /api/v1/chat/ask (API)
    ↓
ChatAgent.run() (Strands)
    ↓
├── ChromaTool.semantic_search() → Top-K relevant code chunks
├── Neo4jTool.code_relationships() → Related functions/classes  
└── BedrockProvider.generate() → AWS Bedrock Claude
    ↓
Response with answer + citations
```

### Key Components

- **`strands/agents/chat_agent.py`** - Main orchestration logic
- **`strands/tools/chroma_tool.py`** - Vector search interface
- **`strands/tools/neo4j_tool.py`** - Graph query interface  
- **`strands/providers/bedrock_provider.py`** - AWS Bedrock client
- **`src/api/routes/chat.py`** - FastAPI endpoints

## Security Notes

- **Credentials**: Never commit AWS credentials to git
- **Costs**: Monitor usage in AWS console to avoid unexpected charges
- **Access**: Use least-privilege IAM roles with only `bedrock:InvokeModel`
- **Data**: Your code is sent to AWS Bedrock - review data policies

---

## Quick Setup Commands

```powershell
# 1. Configure AWS (choose one)
aws configure --profile codebase-rag
# OR set environment variables

# 2. Update .env file
notepad .env
# Add BEDROCK_MODEL_ID and AWS_REGION

# 3. Restart API
.\START.ps1 -Mode api

# 4. Test in browser
start http://localhost:3000/chat
```

**🚀 Your AI Chat should now be ready to answer questions about your codebase!**