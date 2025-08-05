"""
FastAPI application for Codebase RAG system.
Provides RESTful API endpoints for querying, indexing, and managing repositories.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# ChromaDB will be imported dynamically to avoid blocking startup
ChromaDBClient = None
SearchQuery = None
SearchResult = None
    
from .core.neo4j_client import Neo4jClient
from .core.logging_config import setup_logging, log_api_request, get_logger
# Embedding config will be imported dynamically to avoid blocking startup
from .services.repository_processor import RepositoryProcessor, RepositoryConfig, RepositoryFilter
from .services.repository_processor_v2 import EnhancedRepositoryProcessor
# Route imports (enabled for production)
from .api.routes import health, query, index, admin, diagnostics
# from .api.middleware.auth import AuthMiddleware
# from .api.middleware.logging import LoggingMiddleware
from .config.settings import Settings
from . import dependencies

# Extend settings with Bedrock/LLM config attributes if not already present
# We avoid import-time failures by using getattr with defaults.
def _ensure_bedrock_defaults(s: Settings):
    # Required for chat enablement
    if not hasattr(s, "bedrock_model_id"):
        setattr(s, "bedrock_model_id", None)
    if not hasattr(s, "aws_region"):
        setattr(s, "aws_region", None)
    # Optional credential source hints (env or profile)
    if not hasattr(s, "aws_profile"):
        setattr(s, "aws_profile", None)
    if not hasattr(s, "aws_access_key_id"):
        setattr(s, "aws_access_key_id", None)
    if not hasattr(s, "aws_secret_access_key"):
        setattr(s, "aws_secret_access_key", None)
    # LLM budgets and timeouts
    if not hasattr(s, "llm_max_input_tokens"):
        setattr(s, "llm_max_input_tokens", 8000)
    if not hasattr(s, "llm_max_output_tokens"):
        setattr(s, "llm_max_output_tokens", 1024)
    if not hasattr(s, "llm_request_timeout_seconds"):
        setattr(s, "llm_request_timeout_seconds", 30.0)


# Initialize settings
settings = Settings()

# Setup comprehensive logging with enhanced error handling
logger = setup_logging(
    log_level=settings.log_level,
    component="api",
    enable_console=True,
    enable_file=True,
    enable_performance_tracking=True
)

# Import enhanced error handling components EARLY so get_error_handler is defined
from .core.error_handling import handle_api_errors, get_error_handler, get_all_error_handler_stats

# Warm up error handlers early to avoid signature mismatch during import reloads
try:
    # Use only legacy-supported params here (no retry_delay kwarg)
    _ = get_error_handler("initialization", max_retries=2, timeout=120.0)
    _ = get_error_handler("api", max_retries=2, timeout=30.0)
    _ = get_error_handler("database", max_retries=3, timeout=10.0)
    _ = get_error_handler("processing", max_retries=3, timeout=1800.0)
    _ = get_error_handler("health_check", max_retries=1, timeout=5.0)
except TypeError:
    # If an older module version without retry_delay is currently loaded, ignore and proceed
    pass
from .core.performance_metrics import performance_collector
from .core.exceptions import GraphRAGException, ErrorContext
from .core.diagnostics import diagnostic_collector
# Redis client lifecycle
from .core.redis_client import create_redis_client, close_redis_client


async def initialize_clients_async(app: FastAPI):
    """Initialize clients in background without blocking server startup with comprehensive error handling."""
    initialization_start = time.time()
    # Acquire an error handler using legacy-compatible signature (no retry_delay kwarg here)
    try:
        error_handler = get_error_handler("initialization", max_retries=2, timeout=120.0)
    except TypeError:
        # If a stale module version without expanded signature is loaded, fallback to minimal call
        error_handler = get_error_handler("initialization")
    
    try:
        logger.info("=== BACKGROUND INIT: Starting client initialization ===")
        
        # Mark initializing state explicitly so readiness can gate callers
        app.state.is_ready = False
        app.state.initialization_error = None
        
        # Start performance collection
        await performance_collector.start_collection()
        
        # Record initialization start
        performance_collector.record_metric("initialization_start", 1)

        chroma_client = None
        neo4j_client = None
        repository_processor = None
        embedding_client = None

        import os
        # Enforce ChromaDB REQUIRED: ignore CHROMA_DISABLED and always attempt init
        logger.info("=== BACKGROUND INIT: Importing ChromaDB dynamically (required) ===")
        try:
            # Import and create ChromaDB client in separate thread to avoid blocking
            def _import_and_create_chromadb():
                # Import our v2-native client
                from src.core.chromadb_client import ChromaDBClient as V2ChromaDBClient
                # Optional tenant via env CHROMA_TENANT; None means global v2 endpoints
                tenant = os.getenv("CHROMA_TENANT", "").strip() or None
                return V2ChromaDBClient(
                    host=settings.chroma_host,
                    port=settings.chroma_port,
                    collection_name=settings.chroma_collection_name,
                    tenant=tenant,
                )
            # Run ChromaDB import/creation in thread pool to avoid blocking event loop
            chroma_client = await asyncio.to_thread(_import_and_create_chromadb)
            # Ensure the target collection exists (self-healing, v2 endpoints)
            await chroma_client.initialize()
            await chroma_client.get_or_create_collection(
                settings.chroma_collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("ChromaDB v2 client initialized and collection ensured", collection=settings.chroma_collection_name)
        except Exception as e:
            # Treat 409 "collection already exists" as success, not a startup blocker
            msg = str(e)
            if "409" in msg or "already exists" in msg:
                logger.warning("Chroma collection already exists; continuing startup", collection=settings.chroma_collection_name, error=msg)
                # chroma_client should still be valid - don't set initialization_error
            else:
                logger.error(f"ChromaDB initialization failed (required): {e}")
                app.state.initialization_error = f"ChromaDB init failed: {e}"
                chroma_client = None
                # Continue; readiness endpoint will report 'not_ready' until fixed
        
        # Initialize Neo4j client (guard errors but do not raise)
        try:
            neo4j_client = Neo4jClient(
                uri=settings.neo4j_uri,
                username=settings.neo4j_username,
                password=settings.neo4j_password,
                database=settings.neo4j_database
            )
            await neo4j_client.initialize()
        except Exception as e:
            logger.error(f"Neo4j initialization failed: {e}")
            app.state.initialization_error = (app.state.initialization_error or "") + f" | Neo4j init failed: {e}"
            neo4j_client = None
        
        # Initialize Async CodeBERT embedding client - make this NON-BLOCKING and OPTIONAL
        logger.info("=== BACKGROUND INIT: Importing embedding config dynamically ===")
        embedding_client = None
        try:
            def _import_and_create_embedding_client():
                import importlib
                embedding_module = importlib.import_module('.core.embedding_config', package='src')
                create_embedding_client = embedding_module.create_embedding_client
                # IMPORTANT: do NOT pass unsupported kwargs; keep params minimal
                return create_embedding_client(
                    model_type="codebert",
                    device="auto",
                    use_cache=True,
                    cache_size=10000,
                    lazy_init=True
                )
            embedding_client = await asyncio.to_thread(_import_and_create_embedding_client)
            logger.info("Async CodeBERT embedding client created - models will load on first use")
        except Exception as emb_e:
            logger.warning(f"Embedding initialization skipped (non-blocking): {emb_e}")
            embedding_client = None
        
        # Initialize enhanced repository processor v2.0 (thread-free) only if dependencies are present
        if chroma_client and neo4j_client:
            repository_processor = EnhancedRepositoryProcessor(
                chroma_client=chroma_client,
                neo4j_client=neo4j_client,
                max_concurrent_repos=3,  # Conservative for stability
                workspace_dir="./data/repositories",
                use_codebert=(embedding_client is not None)
            )
        else:
            repository_processor = None
            logger.warning("Repository processor not created (missing dependencies)", chroma_ready=bool(chroma_client), neo4j_ready=bool(neo4j_client))
        
        # Set clients in dependencies module
        dependencies.set_clients(chroma_client, neo4j_client, repository_processor, embedding_client)
        
        # Store clients in app state
        app.state.chroma_client = chroma_client
        app.state.neo4j_client = neo4j_client
        app.state.repository_processor = repository_processor
        app.state.embedding_client = embedding_client

        # Validate Bedrock/Chat config strictly to set chat feature flag
        try:
            # Collect minimal config from Settings/environment for validation
            bedrock_config = {
                "BEDROCK_MODEL_ID": getattr(settings, "bedrock_model_id", None),
                "AWS_REGION": getattr(settings, "aws_region", None),
            }

            # Late import to avoid heavy deps at import time
            from .api.routes import chat as _chat_router  # noqa: F401
            from .api.routes.chat import ChatAskRequest as _ChatAskRequest  # noqa: F401
            from ..strands.agents.chat_agent import ChatAgent  # type: ignore
            chat_enabled = ChatAgent.validate(bedrock_config)
            app.state.chat_enabled = bool(chat_enabled)
            if not app.state.chat_enabled:
                logger.warning("Chat feature disabled due to invalid Bedrock config",
                               bedrock_model_id=bedrock_config.get("BEDROCK_MODEL_ID"),
                               aws_region=bedrock_config.get("AWS_REGION"))
            else:
                logger.info("Chat feature enabled (Bedrock config validated)", chat_enabled=True)
        except Exception as e:
            app.state.chat_enabled = False
            logger.warning(f"Chat feature disabled (validation error): {e}")

        # --- FORCE ATTACHMENT SAFEGUARDS AND PROBES (fix readiness stuck with false attachments) ---
        # If clients exist but health checks haven't run yet, perform fast probes to validate and attach.
        try:
            # Chroma quick probe to ensure client is alive and attach into app.state if missing
            if chroma_client and not getattr(app.state, "chroma_client", None):
                app.state.chroma_client = chroma_client
            if chroma_client:
                try:
                    # Fast path: ensure collection still available; treat exceptions with 409/exists as success
                    await asyncio.wait_for(chroma_client.health_check(), timeout=3.0)
                except Exception as ce:
                    msg = str(ce)
                    if "409" in msg or "already exists" in msg:
                        logger.warning("Chroma collection pre-exists; treating probe as healthy")
                    else:
                        logger.error(f"Chroma quick probe failed: {msg}")
                        # Keep initialization_error for visibility
                        app.state.initialization_error = (app.state.initialization_error or "") + f" | Chroma probe: {msg}"
            # Neo4j quick probe to validate bolt connectivity and attach into app.state if missing
            if neo4j_client and not getattr(app.state, "neo4j_client", None):
                app.state.neo4j_client = neo4j_client
            if neo4j_client:
                try:
                    from .core.neo4j_client import GraphQuery
                    _probe = GraphQuery(cypher="RETURN 1 as ok", read_only=True)
                    _ = await asyncio.wait_for(neo4j_client.execute_query(_probe), timeout=3.0)
                except Exception as ne:
                    logger.error(f"Neo4j quick probe failed: {ne}")
                    app.state.initialization_error = (app.state.initialization_error or "") + f" | Neo4j probe: {ne}"
            # Processor is non-blocking; if deps are available and processor missing, attempt lightweight construct
            if (chroma_client and neo4j_client) and (repository_processor is None):
                try:
                    repository_processor = EnhancedRepositoryProcessor(
                        chroma_client=chroma_client,
                        neo4j_client=neo4j_client,
                        max_concurrent_repos=2,
                        workspace_dir="./data/repositories",
                        use_codebert=bool(embedding_client)
                    )
                    app.state.repository_processor = repository_processor
                except Exception as pe:
                    logger.warning(f"Processor construction failed (non-blocking): {pe}")
        except Exception as att_e:
            logger.warning(f"Attachment/probe phase encountered an error: {att_e}")

        # Ready gates ONLY on ChromaDB and Neo4j; processor/embeddings are non-blocking
        app.state.is_ready = bool(chroma_client and neo4j_client)
        
        # Ensure dependencies.* and app.state remain in sync for downstream accessors
        try:
            dependencies.set_clients(chroma_client, neo4j_client, repository_processor, embedding_client)
        except Exception as se:
            logger.warning(f"Dependency injection sync failed: {se}")

        logger.info("🚀 Enhanced GraphRAG v2.0 startup finished",
                   chromadb_available=chroma_client is not None,
                   neo4j_connected=neo4j_client is not None,
                   processor_initialized=repository_processor is not None,
                   processor_version="v2.0_enhanced" if repository_processor else "none",
                   codebert_available=embedding_client is not None,
                   ready=app.state.is_ready)

    except Exception as e:
        # Normalize handler signature drift (e.g., unexpected retry_delay) to avoid aborting startup
        if "retry_delay" in str(e):
            logger.warning(f"Ignoring retry_delay incompatibility in error handler: {e}")
        else:
            logger.error(f"Background initialization failed: {e}")
            # Preserve earlier initialization_error if present
            if not getattr(app.state, "initialization_error", None):
                app.state.initialization_error = str(e)
        # Do not bring the app down; keep running so readiness endpoint can surface diagnostics
        try:
            app.state.is_ready = False
        except Exception:
            pass
        
        # Clean up any partially initialized clients
        if 'chroma_client' in locals() and chroma_client:
            try:
                await chroma_client.close()
            except:
                pass
        if 'neo4j_client' in locals() and neo4j_client:
            try:
                await neo4j_client.close()
            except:
                pass
        if 'repository_processor' in locals() and repository_processor:
            try:
                await repository_processor.cleanup()
            except:
                pass
        if 'embedding_client' in locals() and embedding_client:
            try:
                embedding_client.close()
            except:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with non-blocking initialization."""
    
    # Startup
    logger.info("=== LIFESPAN STARTUP: Starting Codebase RAG application ===", version="1.0.0")
    
    # Initialize ready state
    app.state.is_ready = False
    app.state.initialization_error = None
    # Initialize Redis early and non-blocking for task tracking availability
    try:
        await create_redis_client()
        logger.info("Redis client initialized during lifespan startup")
    except Exception as re:
        # Do not block app start if Redis is unavailable; status endpoints will degrade gracefully
        logger.warning(f"Redis client initialization skipped (non-fatal): {re}")
    
    # Phase 0: Configuration validation (blocking - must pass before proceeding)
    logger.info("=== LIFESPAN: Running configuration validation ===")
    try:
        from .services.config_validator import validate_configuration
        config_summary = await validate_configuration(settings)
        
        # Store configuration validation results
        app.state.config_validation = {
            "overall_success": config_summary.overall_success,
            "total_checks": config_summary.total_checks,
            "passed_checks": config_summary.passed_checks,
            "failed_checks": config_summary.failed_checks,
            "critical_failures": config_summary.critical_failures,
            "error_failures": config_summary.error_failures,
            "warning_failures": config_summary.warning_failures,
            "validation_time": config_summary.validation_time,
            "results": config_summary.results
        }
        
        if config_summary.critical_failures > 0:
            critical_issues = [
                result for result in config_summary.results 
                if not result.success and result.level == "CRITICAL"
            ]
            error_msg = f"Critical configuration failures detected: {len(critical_issues)} issues"
            logger.error(error_msg)
            for issue in critical_issues:
                logger.error(f"  • {issue.component}: {issue.message}")
                if issue.remediation:
                    logger.info(f"    → {issue.remediation}")
            
            app.state.initialization_error = error_msg
            # Still allow server to start but mark as not ready
        else:
            logger.info(f"Configuration validation passed: {config_summary.passed_checks}/{config_summary.total_checks} checks")
            if config_summary.warning_failures > 0:
                logger.warning(f"Configuration has {config_summary.warning_failures} warnings - review recommended")
    
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        app.state.initialization_error = f"Configuration validation error: {e}"
        app.state.config_validation = {
            "overall_success": False,
            "error": str(e)
        }
    
    logger.info("=== LIFESPAN: Creating background initialization task ===")
    # Start background initialization task (non-blocking)
    # Ensure compatibility with older error handler signature during import races:
    try:
        # Warm up default handlers with legacy signature (no retry_delay kwarg passed here)
        _ = get_error_handler("initialization", max_retries=2, timeout=120.0)
    except TypeError:
        # In case an older version without retry_delay is loaded first, ignore
        pass
    except Exception:
        # Guard against unexpected kwargs in downstream implementations (e.g., retry_delay)
        try:
            _ = get_error_handler("initialization")
        except Exception:
            # As a last resort, skip warming to avoid aborting startup
            pass
    initialization_task = asyncio.create_task(initialize_clients_async(app))

    # Allow server to start accepting requests immediately
    logger.info("=== LIFESPAN: Server starting - clients initializing in background ===")

    # Yield control to the application while also ensuring we set minimal attachment flags
    # If the background task already attached clients, reflect that in state before first requests
    try:
        # small grace period to allow immediate init to finish when services are already up
        await asyncio.wait_for(asyncio.shield(initialization_task), timeout=0.25)
    except Exception:
        # expected: still initializing; make sure state fields exist to avoid falsy defaults
        pass
    finally:
        # Mirror dependency module clients to app.state for health endpoint visibility even during init
        try:
            app.state.chroma_client = getattr(dependencies, "chroma_client", getattr(app.state, "chroma_client", None))
            app.state.neo4j_client = getattr(dependencies, "neo4j_client", getattr(app.state, "neo4j_client", None))
            app.state.repository_processor = getattr(dependencies, "repository_processor", getattr(app.state, "repository_processor", None))
            app.state.embedding_client = getattr(dependencies, "embedding_client", getattr(app.state, "embedding_client", None))
        except Exception:
            # do not block startup on state mirroring
            pass

    # Yield control to the application
    yield
    
    # Shutdown
    logging.info("🛑 Shutting down Enhanced GraphRAG v2.0 application...")
    
    # Ensure latest client refs from app.state are closed (avoid stale dependencies.* refs)
    # Close Redis client gracefully
    try:
        await close_redis_client()
    except Exception as re:
        logging.error(f"Error closing Redis client: {re}")
        
    chroma_ref = getattr(app.state, "chroma_client", None) or getattr(dependencies, "chroma_client", None)
    if chroma_ref:
        try:
            await chroma_ref.close()
        except Exception as e:
            logging.error(f"Error closing ChromaDB client: {e}")
    
    neo4j_ref = getattr(app.state, "neo4j_client", None) or getattr(dependencies, "neo4j_client", None)
    if neo4j_ref:
        try:
            await neo4j_ref.close()
        except Exception as e:
            logging.error(f"Error closing Neo4j client: {e}")
    
    proc_ref = getattr(app.state, "repository_processor", None) or getattr(dependencies, "repository_processor", None)
    if proc_ref:
        try:
            await proc_ref.cleanup()
        except Exception as e:
            logging.error(f"Error cleaning up repository processor: {e}")
    
    emb_ref = getattr(app.state, "embedding_client", None) or getattr(dependencies, "embedding_client", None)
    if emb_ref:
        try:
            emb_ref.close()
        except Exception as e:
            logging.error(f"Error closing embedding client: {e}")
    
    logging.info("Application shutdown completed")


# Create FastAPI application
app = FastAPI(
    title="Codebase RAG API",
    description="Advanced RAG system for large-scale codebase analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
# Ensure CORS is permissive for local dev to avoid frontend network errors
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request start
    logger.info(f"Request started: {request.method} {request.url.path}",
               method=request.method,
               path=request.url.path,
               query_params=str(request.query_params) if request.query_params else None,
               client_ip=request.client.host if request.client else None)
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log request completion
    log_api_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=duration,
        client_ip=request.client.host if request.client else None
    )
    
    return response

# if settings.auth_enabled:
#     app.add_middleware(AuthMiddleware)

# Include routers with /api/v1 prefix as per horizon-beta recommendations
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(index.router, prefix="/api/v1/index", tags=["Indexing"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(diagnostics.router, prefix="/api/v1/diagnostics", tags=["Diagnostics"])

# Graph visualization router (ensure registered once under /api/v1/graph)
# Prefer the unified 'graph' router if present; fall back to legacy 'graph_visualization'
graph_router_registered = False
try:
    # Try both absolute and relative to avoid any packaging resolution issues
    try:
        from src.api.routes import graph as graph_router  # absolute import
    except Exception as abs_e:
        logger.info("Absolute import for graph router failed, trying relative", error=str(abs_e))
        from .api.routes import graph as graph_router  # relative import fallback

    # Sanity: router must have attribute 'router'
    if not hasattr(graph_router, "router"):
        raise ImportError("graph module loaded but missing 'router' attribute")

    app.include_router(graph_router.router, prefix="/api/v1/graph", tags=["Graph"])
    logger.info("Graph visualization router registered", path="/api/v1/graph/*", module=str(graph_router))
    graph_router_registered = True
except Exception as e:
    logger.warning("Primary graph router not available", error=str(e))

if not graph_router_registered:
    try:
        from src.api.routes import graph_visualization as graph_vis_router  # if present
        if not hasattr(graph_vis_router, "router"):
            raise ImportError("graph_visualization module missing 'router'")
        app.include_router(graph_vis_router.router, prefix="/api/v1/graph", tags=["Graph"])
        logger.info("Legacy graph visualization router registered", path="/api/v1/graph/*")
        graph_router_registered = True
    except Exception as e:
        logger.error("No graph visualization router registered", error=str(e))

# Migration Planner router (multi-repo canonical plan) - register ONCE
migration_plan_registered = False
try:
    from src.api.routes import migration_plan as migration_plan_router  # lightweight import
    app.include_router(migration_plan_router.router, prefix="/api/v1/migration-plan", tags=["Migration"])
    logger.info("Migration Plan router registered", route="/api/v1/migration-plan")
    migration_plan_registered = True
except Exception as e:
    logger.warning(f"Migration Plan router unavailable: {e}")

# Remove duplicate migration plan registration block (handled above)
# If needed in the future, guard with `if not migration_plan_registered: ...`

# Conditionally include Chat router only when chat is enabled (validated Bedrock config)
try:
   from src.api.routes import chat as chat_router  # lightweight import
   # We gate registration on a runtime flag set during startup validation
   if getattr(app.state, "chat_enabled", False):
       app.include_router(chat_router.router, prefix="/api/v1/chat", tags=["Chat"])
       logger.info("Chat router registered", chat_enabled=True)
   else:
       logger.info("Chat router not registered (chat_enabled is False)")
except Exception as e:
   logger.warning(f"Chat router unavailable: {e}")

# Log management endpoints
@app.get("/api/v1/health/enhanced/neo4j-config")
async def get_neo4j_effective_config():
    """
    Return the effective Neo4j configuration the API is using (MVP: includes password).
    Intended strictly for local troubleshooting in development.
    """
    return {
        "uri": settings.neo4j_uri,
        "username": settings.neo4j_username,
        "password": settings.neo4j_password,
        "database": settings.neo4j_database
    }

@app.get("/api/v1/health/neo4j-probe")
async def neo4j_probe(neo4j: Neo4jClient = Depends(dependencies.get_neo4j_client)):
    """
    Execute a trivial connectivity probe against Neo4j to surface driver errors.
    """
    try:
        test_query = Query(
            cypher="RETURN 1 as test",
            read_only=True
        )
        # Use the client's native GraphQuery wrapper if available
        try:
            from .core.neo4j_client import GraphQuery
            test_query = GraphQuery(cypher="RETURN 1 as test", read_only=True)
        except Exception:
            pass
        result = await neo4j.execute_query(test_query)
        ok = bool(result.records and result.records[0].get("test") == 1)
        return {"status": "ok" if ok else "fail", "records": result.records}
    except Exception as e:
        return {"status": "error", "error": str(e)}
        
@app.get("/api/v1/logs/recent")
async def get_recent_logs(component: Optional[str] = None, limit: int = 100):
    """Get recent log entries."""
    from .core.logging_config import log_aggregator
    return log_aggregator.get_recent_logs(component, limit)

@app.get("/api/v1/logs/errors")
async def get_error_summary(hours: int = 24):
    """Get error summary for the last N hours."""
    from .core.logging_config import log_aggregator
    return log_aggregator.get_error_summary(hours)

@app.post("/api/v1/logs/cleanup")
async def cleanup_old_logs(days: int = 7):
    """Clean up old log files."""
    from .core.logging_config import log_aggregator
    log_aggregator.cleanup_old_logs(days)
    return {"message": f"Cleaned up log files older than {days} days"}


# Root endpoint
@app.get("/api/v1/health/enhanced/state")
async def get_enhanced_state(request: Request):
    """
    Return critical app.state flags useful for diagnosing readiness issues.
    """
    # Add a minimal synchronous hint if deps are reachable but flags not yet mirrored
    chroma_attached = bool(getattr(request.app.state, "chroma_client", None))
    neo4j_attached = bool(getattr(request.app.state, "neo4j_client", None))
    inferred_ready = chroma_attached and neo4j_attached
    return {
        "is_ready": getattr(request.app.state, "is_ready", False) or inferred_ready,
        "initialization_error": getattr(request.app.state, "initialization_error", None),
        "components": {
            "chroma_client": chroma_attached,
            "neo4j_client": neo4j_attached,
            "repository_processor": bool(getattr(request.app.state, "repository_processor", None)),
            "embedding_client": bool(getattr(request.app.state, "embedding_client", None)),
        }
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logging.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )




if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )