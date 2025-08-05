from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import core clients and lifespan managers
from ..core.redis_client import create_redis_client, close_redis_client, get_redis_client

# Routers
from .routes import health as health_routes
from .routes.migration_plan import router as migration_plan_router
from .routes.chat import router as chat_router
from .routes.index import router as index_router
from .routes.cross_repository import router as cross_repository_router
from .routes.admin import router as admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize and connect to Redis
    await create_redis_client()
    yield
    # Shutdown: Gracefully close Redis connection
    await close_redis_client()

def create_app() -> FastAPI:
    app = FastAPI(title="Graf API", version="2.0.0", lifespan=lifespan)

    # CORS - permissive by default; tighten if needed via settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize app state defaults. Real startup elsewhere can override/attach clients.
    app.state.is_ready = False
    app.state.initialization_error = None
    app.state.chroma_client = getattr(app.state, "chroma_client", None)
    app.state.neo4j_client = getattr(app.state, "neo4j_client", None)
    app.state.repository_processor = getattr(app.state, "repository_processor", None)
    app.state.embedding_client = getattr(app.state, "embedding_client", None)

    # Mount canonical health endpoints under /api/v1/health
    app.include_router(health_routes.router, prefix="/api/v1/health", tags=["health"])

    # Provide common aliases for health to avoid frontend brittleness
    # /health/ready and /api/health/ready will also work
    app.include_router(health_routes.router, prefix="/health", tags=["health-alias"])
    app.include_router(health_routes.router, prefix="/api/health", tags=["health-alias"])

    # Mount feature routers (paths assume upstream usage at /api/v1/...)
    app.include_router(migration_plan_router, prefix="/api/v1/migration-plan", tags=["migration-plan"])
    app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
    app.include_router(cross_repository_router, prefix="/api/v1/cross-repository", tags=["cross-repository"])
    app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])

    @app.on_event("startup")
    async def _on_startup():
        # If another initializer attaches real clients, it can also set is_ready True.
        # Here we set is_ready True when core clients exist; otherwise leave False.
        chroma = getattr(app.state, "chroma_client", None)
        neo4j = getattr(app.state, "neo4j_client", None)
        # Processor and embedding are not strictly required to serve basic requests
        if chroma and neo4j:
            app.state.is_ready = True

    return app

app = create_app()