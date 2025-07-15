# Implementation Requirements & Setup Guide

## ChromaDB + Neo4j Solution Implementation

### System Requirements

#### Hardware Requirements
- **Minimum**: 32GB RAM, 8 CPU cores, 1TB SSD storage
- **Recommended**: 128GB RAM, 16 CPU cores, 2TB NVMe SSD
- **Production**: 256GB RAM, 32 CPU cores, 4TB NVMe SSD

#### Software Dependencies

##### Core Components
```bash
# Container Runtime
Docker >= 24.0.0
Docker Compose >= 2.20.0

# Python Runtime
Python >= 3.10
pip >= 23.0

# Node.js (for Tree-sitter bindings)
Node.js >= 18.0.0
npm >= 9.0.0

# Git
Git >= 2.40.0
```

##### Python Dependencies
```python
# Core RAG Components
chromadb >= 0.4.15
sentence-transformers >= 2.2.2
neo4j >= 5.14.0
py2neo >= 2021.2.3

# Code Processing
tree-sitter >= 0.20.4
tree-sitter-python >= 0.20.4
tree-sitter-javascript >= 0.20.2
tree-sitter-typescript >= 0.20.3
tree-sitter-rust >= 0.20.4
tree-sitter-go >= 0.20.0
tree-sitter-java >= 0.20.2
tree-sitter-cpp >= 0.20.0

# API Framework
fastapi >= 0.104.0
uvicorn >= 0.24.0
pydantic >= 2.5.0

# Data Processing
pandas >= 2.1.0
numpy >= 1.24.0
asyncio-mqtt >= 0.13.0

# Monitoring
prometheus-client >= 0.19.0
structlog >= 23.2.0
```

##### System Libraries
```bash
# Ubuntu/Debian
apt-get update
apt-get install -y \
    build-essential \
    python3-dev \
    libssl-dev \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg8-dev \
    zlib1g-dev \
    git \
    curl

# macOS
brew install \
    python \
    node \
    git \
    tree-sitter
```

---

## AWS-Only Solution Implementation

### AWS Services Required

#### Core Services
- **AWS Bedrock**: Foundation models and Knowledge Bases
- **AWS Lambda**: Code processing functions
- **Amazon S3**: Repository storage and artifacts
- **Amazon OpenSearch**: Metadata and relationship indexing
- **AWS IAM**: Access control and security

#### Supporting Services
- **AWS CloudWatch**: Monitoring and logging
- **AWS EventBridge**: Event-driven processing
- **AWS Step Functions**: Workflow orchestration
- **AWS API Gateway**: RESTful API management
- **AWS VPC**: Network isolation and security

### IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:CreateKnowledgeBase",
        "bedrock:GetKnowledgeBase",
        "bedrock:UpdateKnowledgeBase",
        "bedrock:DeleteKnowledgeBase",
        "bedrock:ListKnowledgeBases",
        "bedrock:CreateDataSource",
        "bedrock:GetDataSource",
        "bedrock:UpdateDataSource",
        "bedrock:DeleteDataSource",
        "bedrock:ListDataSources",
        "bedrock:StartIngestionJob",
        "bedrock:GetIngestionJob",
        "bedrock:ListIngestionJobs"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::your-codebase-bucket",
        "arn:aws:s3:::your-codebase-bucket/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "es:ESHttpPost",
        "es:ESHttpPut",
        "es:ESHttpGet",
        "es:ESHttpDelete",
        "es:ESHttpHead"
      ],
      "Resource": "arn:aws:es:region:account:domain/your-opensearch-domain/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction",
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:GetFunction",
        "lambda:DeleteFunction"
      ],
      "Resource": "arn:aws:lambda:region:account:function:codebase-rag-*"
    }
  ]
}
```

### AWS CLI Configuration

```bash
# Install AWS CLI
pip install awscli

# Configure credentials
aws configure set aws_access_key_id YOUR_ACCESS_KEY
aws configure set aws_secret_access_key YOUR_SECRET_KEY
aws configure set default.region us-east-1
aws configure set default.output json

# Install AWS CDK (optional)
npm install -g aws-cdk
```

---

## ChromaDB + Neo4j Detailed Setup

### 1. Environment Setup

#### Create Project Structure
```bash
mkdir -p codebase-rag/{src,docs,tests,config,data,docker}
cd codebase-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

#### Environment Configuration
```bash
# .env file
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_PERSIST_DIRECTORY=./data/chroma

NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080
API_WORKERS=4

# Processing Configuration
MAX_CHUNK_SIZE=1000
OVERLAP_SIZE=200
BATCH_SIZE=100
MAX_CONCURRENT_REPOS=10

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 2. Docker Infrastructure

#### Docker Compose Configuration
```yaml
# docker-compose.yml
version: '3.8'

services:
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data/chroma:/chroma/chroma
    environment:
      - CHROMA_SERVER_AUTHN_CREDENTIALS_FILE=/chroma/auth.txt
      - CHROMA_SERVER_AUTHN_PROVIDER=chromadb.auth.basic_authn.BasicAuthenticationServerProvider
    networks:
      - codebase-rag-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3

  neo4j:
    image: neo4j:5.14-enterprise
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/your_password
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.*
      - NEO4J_dbms_memory_heap_initial_size=2G
      - NEO4J_dbms_memory_heap_max_size=4G
    volumes:
      - ./data/neo4j/data:/data
      - ./data/neo4j/logs:/logs
      - ./data/neo4j/import:/import
      - ./data/neo4j/plugins:/plugins
    networks:
      - codebase-rag-network
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "your_password", "MATCH () RETURN count(*) as count"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - ./data/redis:/data
    networks:
      - codebase-rag-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    ports:
      - "8080:8080"
    depends_on:
      chromadb:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - CHROMA_HOST=chromadb
      - NEO4J_URI=bolt://neo4j:7687
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./data/repositories:/app/data/repositories
      - ./logs:/app/logs
    networks:
      - codebase-rag-network

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    depends_on:
      chromadb:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      - CHROMA_HOST=chromadb
      - NEO4J_URI=bolt://neo4j:7687
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./data/repositories:/app/data/repositories
      - ./logs:/app/logs
    networks:
      - codebase-rag-network
    scale: 4

  monitor:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./data/prometheus:/prometheus
    networks:
      - codebase-rag-network

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - ./data/grafana:/var/lib/grafana
      - ./config/grafana:/etc/grafana/provisioning
    networks:
      - codebase-rag-network

networks:
  codebase-rag-network:
    driver: bridge

volumes:
  chroma_data:
  neo4j_data:
  redis_data:
  prometheus_data:
  grafana_data:
```

### 3. Application Structure

#### Core Application Components
```
src/
├── __init__.py
├── main.py                 # FastAPI application entry point
├── config/
│   ├── __init__.py
│   ├── settings.py         # Configuration management
│   └── logging.py          # Logging configuration
├── core/
│   ├── __init__.py
│   ├── chromadb_client.py  # ChromaDB integration
│   ├── neo4j_client.py     # Neo4j integration
│   └── embeddings.py       # Embedding management
├── processing/
│   ├── __init__.py
│   ├── tree_sitter_parser.py  # AST parsing
│   ├── code_chunker.py     # Intelligent code chunking
│   ├── repository_processor.py  # Repository processing
│   └── relationship_extractor.py  # Business logic extraction
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── query.py        # Query endpoints
│   │   ├── index.py        # Indexing endpoints
│   │   └── health.py       # Health check endpoints
│   └── middleware/
│       ├── __init__.py
│       ├── auth.py         # Authentication
│       └── logging.py      # Request logging
├── services/
│   ├── __init__.py
│   ├── retrieval_service.py  # Multi-modal retrieval
│   ├── indexing_service.py   # Repository indexing
│   └── monitoring_service.py # Performance monitoring
└── utils/
    ├── __init__.py
    ├── git_utils.py        # Git operations
    ├── file_utils.py       # File processing
    └── async_utils.py      # Async utilities
```

### 4. Installation Steps

#### Step 1: Clone and Setup
```bash
# Clone repository
git clone <repository-url>
cd codebase-rag

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Step 2: Infrastructure Setup
```bash
# Create data directories
mkdir -p data/{chroma,neo4j,redis,prometheus,grafana}
mkdir -p logs

# Set permissions
chmod 755 data/
chmod 755 logs/

# Start infrastructure
docker-compose up -d chromadb neo4j redis

# Wait for services to be healthy
docker-compose ps
```

#### Step 3: Database Initialization
```bash
# Initialize Neo4j schema
python scripts/init_neo4j_schema.py

# Initialize ChromaDB collections
python scripts/init_chromadb_collections.py

# Verify setup
python scripts/verify_setup.py
```

#### Step 4: Configuration Validation
```bash
# Test ChromaDB connection
python -c "from src.core.chromadb_client import ChromaDBClient; client = ChromaDBClient(); print('ChromaDB OK')"

# Test Neo4j connection
python -c "from src.core.neo4j_client import Neo4jClient; client = Neo4jClient(); print('Neo4j OK')"

# Test Tree-sitter parsers
python -c "from src.processing.tree_sitter_parser import TreeSitterParser; parser = TreeSitterParser(); print('Tree-sitter OK')"
```

### 5. Development Environment

#### IDE Configuration
```json
// .vscode/settings.json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": [
    "tests"
  ],
  "files.exclude": {
    "**/__pycache__": true,
    "**/.pytest_cache": true,
    "**/venv": true
  }
}
```

#### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.9.1
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203]
```

---

## AWS-Only Solution Setup

### 1. Infrastructure as Code

#### CDK Stack Definition
```typescript
// lib/codebase-rag-stack.ts
import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as opensearch from 'aws-cdk-lib/aws-opensearch';

export class CodebaseRagStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 bucket for repository storage
    const repositoryBucket = new s3.Bucket(this, 'RepositoryBucket', {
      bucketName: 'codebase-rag-repositories',
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // OpenSearch domain for metadata
    const searchDomain = new opensearch.Domain(this, 'SearchDomain', {
      version: opensearch.EngineVersion.OPENSEARCH_2_9,
      capacity: {
        dataNodes: 3,
        dataNodeInstanceType: 'm6g.large.search',
        masterNodes: 3,
        masterNodeInstanceType: 'm6g.medium.search',
      },
      ebs: {
        volumeSize: 100,
        volumeType: ec2.EbsDeviceVolumeType.GP3,
      },
    });

    // Lambda function for code processing
    const processingFunction = new lambda.Function(this, 'ProcessingFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset('lambda/processing'),
      timeout: cdk.Duration.minutes(15),
      memorySize: 3008,
      environment: {
        REPOSITORY_BUCKET: repositoryBucket.bucketName,
        OPENSEARCH_ENDPOINT: searchDomain.domainEndpoint,
      },
    });

    // Grant permissions
    repositoryBucket.grantReadWrite(processingFunction);
    searchDomain.grantIndexReadWrite('*', processingFunction);

    // API Gateway
    const api = new apigateway.RestApi(this, 'CodebaseRagApi', {
      restApiName: 'Codebase RAG API',
      description: 'API for codebase RAG queries',
    });

    // Lambda integration
    const processingIntegration = new apigateway.LambdaIntegration(processingFunction);
    api.root.addResource('query').addMethod('POST', processingIntegration);
  }
}
```

#### CDK Deployment
```bash
# Install CDK
npm install -g aws-cdk

# Initialize CDK project
cdk init app --language typescript

# Install dependencies
npm install

# Deploy infrastructure
cdk deploy --require-approval never
```

### 2. Lambda Functions

#### Processing Function Structure
```
lambda/
├── processing/
│   ├── lambda_function.py      # Main handler
│   ├── tree_sitter_parser.py   # AST parsing
│   ├── bedrock_client.py       # Bedrock integration
│   ├── opensearch_client.py    # OpenSearch integration
│   └── requirements.txt        # Dependencies
├── query/
│   ├── lambda_function.py      # Query handler
│   ├── retrieval_service.py    # Multi-source retrieval
│   └── requirements.txt        # Dependencies
└── layers/
    ├── tree-sitter-layer/      # Tree-sitter binaries
    └── dependencies-layer/     # Common dependencies
```

#### Lambda Layer Creation
```bash
# Create Tree-sitter layer
mkdir -p lambda/layers/tree-sitter-layer/python/lib/python3.11/site-packages
cd lambda/layers/tree-sitter-layer/python/lib/python3.11/site-packages

# Install Tree-sitter and language parsers
pip install tree-sitter tree-sitter-python tree-sitter-javascript -t .

# Create layer zip
cd ../../../..
zip -r tree-sitter-layer.zip python/

# Upload layer
aws lambda publish-layer-version \
  --layer-name tree-sitter-layer \
  --zip-file fileb://tree-sitter-layer.zip \
  --compatible-runtimes python3.11
```

### 3. Bedrock Configuration

#### Knowledge Base Setup
```python
# scripts/setup_bedrock_kb.py
import boto3
from botocore.exceptions import ClientError

def create_knowledge_base():
    bedrock = boto3.client('bedrock-agent')
    
    try:
        response = bedrock.create_knowledge_base(
            name='codebase-rag-kb',
            description='Knowledge base for codebase RAG',
            roleArn='arn:aws:iam::account:role/BedrockKnowledgeBaseRole',
            knowledgeBaseConfiguration={
                'type': 'VECTOR',
                'vectorKnowledgeBaseConfiguration': {
                    'embeddingModelArn': 'arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v1',
                    'embeddingModelConfiguration': {
                        'bedrockEmbeddingModelConfiguration': {
                            'dimensions': 1536
                        }
                    }
                }
            },
            storageConfiguration={
                'type': 'OPENSEARCH_SERVERLESS',
                'opensearchServerlessConfiguration': {
                    'collectionArn': 'arn:aws:aoss:us-east-1:account:collection/codebase-rag',
                    'vectorIndexName': 'codebase-index',
                    'fieldMapping': {
                        'vectorField': 'vector',
                        'textField': 'text',
                        'metadataField': 'metadata'
                    }
                }
            }
        )
        
        print(f"Knowledge base created: {response['knowledgeBase']['knowledgeBaseId']}")
        return response['knowledgeBase']['knowledgeBaseId']
        
    except ClientError as e:
        print(f"Error creating knowledge base: {e}")
        raise

if __name__ == "__main__":
    create_knowledge_base()
```

### 4. Deployment Scripts

#### Automated Deployment
```bash
#!/bin/bash
# scripts/deploy_aws_solution.sh

set -e

echo "Deploying AWS Codebase RAG Solution..."

# Deploy CDK stack
echo "Deploying infrastructure..."
cdk deploy --require-approval never

# Create Lambda layers
echo "Creating Lambda layers..."
./scripts/create_lambda_layers.sh

# Setup Bedrock Knowledge Base
echo "Setting up Bedrock Knowledge Base..."
python scripts/setup_bedrock_kb.py

# Deploy Lambda functions
echo "Deploying Lambda functions..."
./scripts/deploy_lambda_functions.sh

# Configure API Gateway
echo "Configuring API Gateway..."
python scripts/configure_api_gateway.py

echo "Deployment complete!"
echo "API Endpoint: https://$(aws apigateway get-rest-apis --query 'items[?name==`Codebase RAG API`].id' --output text).execute-api.us-east-1.amazonaws.com/prod"
```

---

## Monitoring and Observability

### Metrics Collection
```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Query metrics
query_counter = Counter('rag_queries_total', 'Total RAG queries', ['status'])
query_duration = Histogram('rag_query_duration_seconds', 'Query duration')
active_connections = Gauge('rag_active_connections', 'Active connections')

# Indexing metrics
indexing_counter = Counter('rag_indexing_total', 'Total indexing operations', ['repo', 'status'])
indexing_duration = Histogram('rag_indexing_duration_seconds', 'Indexing duration')
indexed_documents = Gauge('rag_indexed_documents', 'Total indexed documents')

# Performance metrics
retrieval_duration = Histogram('rag_retrieval_duration_seconds', 'Retrieval duration')
embedding_duration = Histogram('rag_embedding_duration_seconds', 'Embedding duration')
```

### Health Checks
```python
# Health check endpoints
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@app.get("/ready")
async def readiness_check():
    checks = {
        "chromadb": await check_chromadb_health(),
        "neo4j": await check_neo4j_health(),
        "redis": await check_redis_health()
    }
    
    if all(checks.values()):
        return {"status": "ready", "checks": checks}
    else:
        raise HTTPException(status_code=503, detail={"status": "not ready", "checks": checks})
```

---

## Security Considerations

### Authentication & Authorization
```python
# JWT-based authentication
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Role-based access control
def require_role(required_role: str):
    def role_checker(token_payload: dict = Depends(verify_token)):
        if token_payload.get("role") != required_role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return token_payload
    return role_checker
```

### Data Protection
```python
# Encryption at rest
from cryptography.fernet import Fernet

class EncryptionService:
    def __init__(self, key: bytes):
        self.fernet = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        return self.fernet.decrypt(encrypted_data.encode()).decode()
```

---

## Performance Optimization

### ChromaDB Optimization
```python
# Optimize ChromaDB settings
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(
    path="./data/chroma",
    settings=Settings(
        chroma_db_impl="duckdb+parquet",
        persist_directory="./data/chroma",
        anonymized_telemetry=False,
        allow_reset=True
    )
)

# Batch operations
def batch_insert_documents(collection, documents, batch_size=1000):
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        collection.add(
            documents=[doc["content"] for doc in batch],
            metadatas=[doc["metadata"] for doc in batch],
            ids=[doc["id"] for doc in batch]
        )
```

### Neo4j Optimization
```cypher
// Create indexes for performance
CREATE INDEX repo_name_index FOR (r:Repository) ON (r.name);
CREATE INDEX file_path_index FOR (f:File) ON (f.path);
CREATE INDEX function_name_index FOR (fn:Function) ON (fn.name);

// Optimize queries with constraints
CREATE CONSTRAINT repo_unique FOR (r:Repository) REQUIRE r.name IS UNIQUE;
CREATE CONSTRAINT file_unique FOR (f:File) REQUIRE f.path IS UNIQUE;
```

---

## Testing Strategy

### Unit Tests
```python
# tests/test_tree_sitter_parser.py
import pytest
from src.processing.tree_sitter_parser import TreeSitterParser

class TestTreeSitterParser:
    def setup_method(self):
        self.parser = TreeSitterParser()
    
    def test_parse_python_function(self):
        code = """
def hello_world():
    print("Hello, World!")
        """
        result = self.parser.parse(code, "python")
        assert result["type"] == "function"
        assert result["name"] == "hello_world"
    
    def test_parse_javascript_class(self):
        code = """
class Calculator {
    add(a, b) {
        return a + b;
    }
}
        """
        result = self.parser.parse(code, "javascript")
        assert result["type"] == "class"
        assert result["name"] == "Calculator"
```

### Integration Tests
```python
# tests/test_integration.py
import pytest
from src.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

class TestIntegration:
    def test_full_indexing_pipeline(self):
        # Test repository indexing
        response = client.post("/api/v1/index", json={
            "repository_url": "https://github.com/example/repo",
            "branch": "main"
        })
        assert response.status_code == 202
        
        # Test querying
        response = client.post("/api/v1/query", json={
            "query": "How to implement authentication?",
            "repository": "example/repo"
        })
        assert response.status_code == 200
        assert "results" in response.json()
```

---

## Troubleshooting Guide

### Common Issues

#### ChromaDB Connection Issues
```python
# Check ChromaDB health
import requests

try:
    response = requests.get("http://localhost:8000/api/v1/heartbeat")
    if response.status_code == 200:
        print("ChromaDB is healthy")
    else:
        print(f"ChromaDB health check failed: {response.status_code}")
except ConnectionError:
    print("Cannot connect to ChromaDB")
```

#### Neo4j Connection Issues
```python
# Check Neo4j connectivity
from neo4j import GraphDatabase

try:
    driver = GraphDatabase.driver("bolt://localhost:7687", 
                                 auth=("neo4j", "password"))
    with driver.session() as session:
        result = session.run("RETURN 1 as test")
        print("Neo4j connection successful")
    driver.close()
except Exception as e:
    print(f"Neo4j connection failed: {e}")
```

#### Memory Issues
```bash
# Monitor memory usage
docker stats --no-stream

# Adjust container memory limits
docker-compose up -d --force-recreate
```

### Performance Tuning

#### ChromaDB Performance
```python
# Optimize collection settings
collection = client.get_or_create_collection(
    name="codebase",
    metadata={"hnsw:space": "cosine", "hnsw:M": 16}
)

# Use batch operations
collection.add(
    documents=documents,
    metadatas=metadatas,
    ids=ids
)
```

#### Neo4j Performance
```cypher
// Monitor query performance
CALL db.stats.retrieve('GRAPH COUNTS');

// Optimize memory settings
CALL dbms.changePassword('newpassword');
```

---

## Maintenance Procedures

### Regular Maintenance Tasks

#### Daily
- Monitor system health and performance metrics
- Check error logs for anomalies
- Verify backup completion

#### Weekly
- Review and optimize slow queries
- Update repository indices for active repositories
- Clean up temporary files and logs

#### Monthly
- Performance benchmarking and optimization
- Security updates and patches
- Capacity planning review

### Backup and Recovery

#### ChromaDB Backup
```bash
# Backup ChromaDB data
tar -czf chromadb-backup-$(date +%Y%m%d).tar.gz ./data/chroma/

# Restore ChromaDB data
tar -xzf chromadb-backup-20240101.tar.gz -C ./data/
```

#### Neo4j Backup
```bash
# Backup Neo4j database
docker exec neo4j neo4j-admin database dump --to-path=/backups neo4j

# Restore Neo4j database
docker exec neo4j neo4j-admin database load --from-path=/backups neo4j
```

This comprehensive implementation guide provides all the necessary requirements, configurations, and procedures for both architectural approaches, with detailed focus on the ChromaDB+Neo4j solution as requested.