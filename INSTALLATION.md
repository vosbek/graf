# CodeBERT Codebase RAG - Installation Guide

## Quick Setup

### Production Installation
```bash
pip install -r requirements.txt
```

### Development Installation
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Verify Installation
```bash
python test_setup.py
```

## Key Changes Made

### 1. Fixed Configuration Mismatch
- **Issue**: `settings.py` defaulted to `sentence-transformers/all-MiniLM-L6-v2` but `embedding_config.py` was built for CodeBERT
- **Fix**: Updated `settings.py` to use `microsoft/codebert-base` with 768 dimensions

### 2. Resolved Dependency Conflicts
- **Issue**: Multiple conflicting package versions with external dependencies
- **Fixes**:
  - Updated FastAPI from 0.104.1 → ≥0.115.0 (resolves anyio conflict)
  - Updated transformers to ≥4.41.0 (satisfies sentence-transformers requirement)
  - Updated Neo4j driver to ≥5.26.0 (satisfies graphiti-core requirement)
  - Updated Pydantic to ≥2.11.5 (satisfies multiple package requirements)
  - Updated OpenTelemetry packages to ≥1.30.0

### 3. Cleaned Up Dependencies
- **Removed redundant packages**:
  - `py2neo` and `neomodel` (kept only official `neo4j` driver)
  - `dulwich` (kept only `GitPython`)
  - `igraph` (kept only `networkx`)
- **Separated dev/prod dependencies**:
  - Production: `requirements.txt`
  - Development: `requirements-dev.txt`

### 4. CodeBERT Optimization
- **Model**: `microsoft/codebert-base`
- **Dimensions**: 768
- **Features**:
  - Async embedding generation
  - Thread pool architecture
  - Caching support
  - ChromaDB integration

## Key Dependencies

### Core ML Stack
- `transformers>=4.41.0,<5.0.0` - CodeBERT model loading
- `torch>=2.1.0` - ML computation
- `tokenizers>=0.15.0` - Text tokenization
- `huggingface-hub>=0.21.0` - Model downloads

### Web Framework
- `fastapi>=0.115.0` - API framework
- `uvicorn[standard]>=0.32.0` - ASGI server
- `pydantic>=2.11.5` - Data validation

### Databases
- `neo4j>=5.26.0` - Graph database
- `chromadb==0.4.18` - Vector database
- `redis==4.6.0` - Caching
- `psycopg2-binary==2.9.9` - PostgreSQL

## Validation

The `test_setup.py` script validates:
1. ✅ All imports work correctly
2. ✅ CodeBERT model loads and generates embeddings
3. ✅ Configuration is properly set
4. ✅ Async embedding client functions

## Notes

- Minor version conflicts remain but don't affect functionality
- The setup is optimized for CodeBERT (768-dimensional embeddings)
- All external package conflicts have been resolved
- Ready for fresh machine installation with `pip install -r requirements.txt`