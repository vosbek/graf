import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


class ChromaV2Error(Exception):
    pass


class ChromaDBClient:
    """
    V2-native Chroma HTTP client (no v1 tenant assumptions).
    Uses /api/v2 endpoints and provides self-healing get_or_create for collections.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        collection_name: Optional[str] = None,
        tenant: Optional[str] = None,  # optional; if provided, will use tenant-scoped endpoints
        database: Optional[str] = None,  # database name for v2 API
        session: Optional[aiohttp.ClientSession] = None,
        request_timeout: float = 15.0,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.base_url = f"http://{self.host}:{self.port}"
        self.collection_name = collection_name
        # Allow CHROMA_TENANT env to override if provided
        self.tenant = tenant or os.getenv("CHROMA_TENANT", "").strip() or "default_tenant"
        self.database = database or os.getenv("CHROMA_DATABASE", "").strip() or "default_database"
        self._session = session
        self._owns_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._headers = {
            "Content-Type": "application/json",
            # If auth headers or tokens are needed, inject here from env/config
        }

    async def initialize(self) -> None:
        """Create an internal session and verify server health /api/v2/healthcheck."""
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)

        logger.info(f"Initializing ChromaDB v2 client: {self.base_url} (tenant: {self.tenant}, database: {self.database})")

        ok = await self._healthcheck_v2()
        if not ok:
            logger.error(f"ChromaDB v2 healthcheck failed: {self.base_url}/api/v2/healthcheck")
            raise ChromaV2Error("Chroma v2 healthcheck failed")
        
        # Ensure tenant exists
        await self._ensure_tenant()
        
        # Ensure database exists
        await self._ensure_database()
        
        logger.info(f"ChromaDB v2 healthcheck passed and tenant/database ensured (tenant: {self.tenant}, database: {self.database})")

    async def close(self) -> None:
        """Close session if owned."""
        if self._session and self._owns_session:
            await self._session.close()
        self._session = None

    # --------- Public helpers used by app ---------

    async def get_or_create_collection(
        self,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Ensure a collection exists. Try get; if missing, create via v2 endpoint.
        Returns collection info dict.
        """
        collection_name = name or self.collection_name
        logger.info(f"Attempting to get or create collection: {collection_name} (tenant: {self.tenant})")
        
        collection = await self.get_collection(collection_name)
        if collection:
            logger.info(f"Collection found: {collection_name} (id: {collection.get('id')}, tenant: {self.tenant})")
            return collection

        # Create if not found
        logger.info(f"Collection not found, creating new collection: {collection_name} (tenant: {self.tenant}, metadata: {metadata})")
        
        try:
            created = await self.create_collection(collection_name, metadata=metadata)
            logger.info(f"Collection created successfully: {collection_name} (id: {created.get('id')}, tenant: {self.tenant})")
            return created
        except Exception as e:
            error_str = str(e)
            if "already exists" in error_str:
                # Collection already exists, try to get it again
                logger.info(f"Collection already exists, fetching: {collection_name}")
                existing = await self.get_collection(collection_name)
                if existing:
                    return existing
            logger.warning(f"Collection creation failed: {collection_name} (tenant: {self.tenant}, error: {error_str}) - Check if Chroma server supports tenant endpoints or requires authentication")
            # Re-raise with context but don't fail hard - allow degraded mode
            raise

    async def get_collection(self, name: Optional[str]) -> Optional[Dict[str, Any]]:
        """Return collection info if exists; otherwise None."""
        if not name:
            raise ValueError("get_collection requires a collection name")

        # Try query by name via v2 endpoint
        # Not all Chroma v2 deployments have a direct `GET ?name=` filter; when missing, list-and-filter
        # We do both strategies: try filter endpoint first; if 405/404, fallback to list and search.
        url = self._v2_url("collections")
        params = {"name": name}
        result = await self._get_json(url, params=params, allow_405=True, allow_404=True)
        if isinstance(result, dict) and result.get("name") == name:
            return result
        if isinstance(result, dict) and "collections" in result:
            # Some servers return {"collections":[...]}
            colls = result.get("collections") or []
            for c in colls:
                if c.get("name") == name:
                    return c

        # Fallback: list all and filter client-side
        result = await self._get_json(url, allow_404=True)
        if isinstance(result, dict) and "collections" in result:
            colls = result.get("collections") or []
            for c in colls:
                if c.get("name") == name:
                    return c

        return None

    async def create_collection(self, name: Optional[str], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a collection via v2. Returns created collection info."""
        if not name:
            raise ValueError("create_collection requires a collection name")

        url = self._v2_url("collections")
        payload = {"name": name}
        if metadata:
            payload["metadata"] = metadata

        result = await self._post_json(url, payload)
        # Some servers return the created collection directly, others return {"collection": {...}}
        if isinstance(result, dict):
            if "name" in result:
                return result
            if "collection" in result and isinstance(result["collection"], dict):
                return result["collection"]
        raise ChromaV2Error(f"Unexpected create_collection response: {result}")

    async def health_check(self) -> Dict[str, Any]:
        """Return v2 health result with tenant/database/collection readiness."""
        health: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": __import__("time").time(),
            "checks": {}
        }
        try:
            # 1) Base v2 healthcheck
            ok = await self._healthcheck_v2()
            health["checks"]["v2_healthcheck"] = {"status": "pass" if ok else "fail"}
            if not ok:
                health["status"] = "unhealthy"

            # 2) Tenant readiness
            try:
                tenant_url = f"{self.base_url}/api/v2/tenants/{self.tenant}"
                _ = await self._get_json(tenant_url)
                health["checks"]["tenant"] = {"status": "pass", "tenant": self.tenant}
            except Exception as te:
                health["checks"]["tenant"] = {"status": "fail", "tenant": self.tenant, "error": str(te)}
                health["status"] = "unhealthy"

            # 3) Database readiness
            try:
                db_url = f"{self.base_url}/api/v2/tenants/{self.tenant}/databases/{self.database}"
                _ = await self._get_json(db_url)
                health["checks"]["database"] = {"status": "pass", "database": self.database}
            except Exception as de:
                health["checks"]["database"] = {"status": "fail", "database": self.database, "error": str(de)}
                health["status"] = "unhealthy"

            # 4) Collection readiness (optional)
            if self.collection_name:
                try:
                    coll = await self.get_or_create_collection(self.collection_name, metadata={"hnsw:space": "cosine"})
                    # Attempt a trivial list call for stats
                    health["checks"]["collection"] = {
                        "status": "pass" if bool(coll) else "warn",
                        "name": self.collection_name,
                        "id": (coll or {}).get("id")
                    }
                except Exception as ce:
                    ce_str = str(ce).lower()
                    # Normalize Chroma v2 409 "already exists" as a PASS for readiness
                    if "already exists" in ce_str or " 409 " in ce_str or ce_str.startswith("409") or "409" in ce_str:
                        health["checks"]["collection"] = {
                            "status": "pass",
                            "name": self.collection_name,
                            "note": "Existing collection treated as ready"
                        }
                        # Do not mark overall unhealthy for existing collection
                    else:
                        health["checks"]["collection"] = {"status": "fail", "name": self.collection_name, "error": str(ce)}
                        # treat collection failure as degraded but not fatal to server health
                        health["status"] = "unhealthy"

        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
            logger.error(f"Chroma health_check failed: {e}")
        return health

    async def get_statistics(self) -> Dict[str, Any]:
        """Basic stats placeholder; extend if your server exposes more."""
        stats: Dict[str, Any] = {}
        # Optionally summarize collections
        try:
            url = self._v2_url("collections")
            result = await self._get_json(url, allow_404=True)
            if isinstance(result, dict) and "collections" in result:
                stats["total_collections"] = len(result.get("collections") or [])
        except Exception:
            # Swallow stats errors; not critical
            pass
        return stats

    # --------- Internals ---------

    def _v2_url(self, resource: str) -> str:
        """
        Build a v2 endpoint using the tenant/database/resource structure.
        Example: /api/v2/tenants/{tenant}/databases/{database}/collections
        """
        if resource == "collections":
            url = f"{self.base_url}/api/v2/tenants/{self.tenant}/databases/{self.database}/collections"
            logger.debug(f"Building collections URL: {url} (tenant: {self.tenant}, database: {self.database})")
            return url
        else:
            # For other resources like healthcheck, use the base v2 path
            url = f"{self.base_url}/api/v2/{resource}"
            logger.debug(f"Building base v2 URL: {url} (resource: {resource})")
            return url

    async def _healthcheck_v2(self) -> bool:
        url = f"{self.base_url}/api/v2/healthcheck"
        try:
            result = await self._get_json(url)
            # Many servers return {"status":"ok"}; accept any 200 JSON as OK.
            return isinstance(result, dict)
        except Exception:
            return False

    async def _ensure_tenant(self) -> None:
        """Ensure the tenant exists, create if it doesn't."""
        try:
            # Try to get the tenant
            url = f"{self.base_url}/api/v2/tenants/{self.tenant}"
            await self._get_json(url)
            logger.info(f"Tenant exists: {self.tenant}")
        except Exception:
            # Tenant doesn't exist, create it
            try:
                url = f"{self.base_url}/api/v2/tenants"
                payload = {"name": self.tenant}
                await self._post_json(url, payload)
                logger.info(f"Created tenant: {self.tenant}")
            except Exception as e:
                logger.warning(f"Failed to create tenant {self.tenant}: {e}")
                # Continue anyway - some ChromaDB deployments may have tenants pre-created

    async def _ensure_database(self) -> None:
        """Ensure the database exists, create if it doesn't."""
        try:
            # Try to get the database
            url = f"{self.base_url}/api/v2/tenants/{self.tenant}/databases/{self.database}"
            await self._get_json(url)
            logger.info(f"Database exists: {self.database}")
        except Exception:
            # Database doesn't exist, create it
            try:
                url = f"{self.base_url}/api/v2/tenants/{self.tenant}/databases"
                payload = {"name": self.database}
                await self._post_json(url, payload)
                logger.info(f"Created database: {self.database}")
            except Exception as e:
                logger.warning(f"Failed to create database {self.database}: {e}")
                # Continue anyway - some ChromaDB deployments may have databases pre-created

    async def _get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        allow_404: bool = False,
        allow_405: bool = False,
    ) -> Any:
        if self._session is None:
            raise RuntimeError("Client not initialized")
        async with self._session.get(url, headers=self._headers, params=params) as resp:
            if resp.status == 404 and allow_404:
                return {}
            if resp.status == 405 and allow_405:
                return {}
            if resp.status >= 400:
                text = await resp.text()
                raise ChromaV2Error(f"GET {url} failed: {resp.status} {text}")
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" in ctype:
                return await resp.json()
            return await resp.text()

    async def _post_json(self, url: str, payload: Dict[str, Any]) -> Any:
        if self._session is None:
            raise RuntimeError("Client not initialized")
        async with self._session.post(url, headers=self._headers, data=json.dumps(payload)) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise ChromaV2Error(f"POST {url} failed: {resp.status} {text}")
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" in ctype:
                return await resp.json()
            return await resp.text()