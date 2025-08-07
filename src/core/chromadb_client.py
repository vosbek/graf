import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class ChromaV2Error(Exception):
    pass


class CompatibilityClient:
    """Compatibility wrapper for old health check code that expects .client attribute."""
    
    def __init__(self, parent_client):
        self.parent = parent_client
    
    def list_collections(self):
        """Synchronous wrapper for list_collections - used by health check."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, but the health check calls this synchronously
                # Create a new thread to handle the async call
                import threading
                result = None
                exception = None
                
                def run_async():
                    nonlocal result, exception
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result = new_loop.run_until_complete(self.parent.list_collections())
                        new_loop.close()
                    except Exception as e:
                        exception = e
                
                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join(timeout=10)  # 10 second timeout
                
                if exception:
                    raise exception
                return result or []
            else:
                return loop.run_until_complete(self.parent.list_collections())
        except Exception:
            return []


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
        tenant_env = os.getenv("CHROMA_TENANT", "").strip()
        database_env = os.getenv("CHROMA_DATABASE", "").strip()
        
        # Support both v1 (no tenant) and v2 (with tenant) modes
        self.tenant = tenant or tenant_env or None
        self.database = database or database_env or None
        self.use_v1_mode = self.tenant is None
        self._session = session
        self._owns_session = session is None
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)
        self._headers = {
            "Content-Type": "application/json",
            # If auth headers or tokens are needed, inject here from env/config
        }
        
        # Compatibility property for old health check code
        self.client = CompatibilityClient(self)

    async def initialize(self) -> None:
        """Create an internal session and verify server health."""
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)

        mode = "v1 (standalone)" if self.use_v1_mode else f"v2 (tenant: {self.tenant}, database: {self.database})"
        logger.info(f"Initializing ChromaDB client: {self.base_url} - {mode}")

        # Use appropriate healthcheck for the mode
        if self.use_v1_mode:
            ok = await self._healthcheck_v1()
            if not ok:
                logger.error(f"ChromaDB v1 healthcheck failed")
                raise ChromaV2Error("ChromaDB v1 healthcheck failed")
        else:
            ok = await self._healthcheck_v2()
            if not ok:
                logger.error(f"ChromaDB v2 healthcheck failed")
                raise ChromaV2Error("ChromaDB v2 healthcheck failed")
            # Only ensure tenant/database in v2 mode
            await self._ensure_tenant()
            await self._ensure_database()
        
        logger.info(f"ChromaDB healthcheck passed - using {mode}")

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
        Ensure a collection exists with robust race condition handling.
        Try get; if missing, create via v2 endpoint with retries.
        Returns collection info dict.
        """
        import asyncio
        
        collection_name = name or self.collection_name
        logger.info(f"Attempting to get or create collection: {collection_name} (tenant: {self.tenant})")
        
        # Retry mechanism for race condition handling
        max_retries = 3
        for attempt in range(max_retries):
            # First, try to get the collection
            collection = await self.get_collection(collection_name)
            if collection:
                logger.info(f"Collection found: {collection_name} (id: {collection.get('id')}, tenant: {self.tenant})")
                return collection

            # Collection doesn't exist, try to create it
            logger.info(f"Collection not found, creating new collection: {collection_name} (tenant: {self.tenant}, metadata: {metadata})")
            
            try:
                created = await self.create_collection(collection_name, metadata=metadata)
                logger.info(f"Collection created successfully: {collection_name} (id: {created.get('id')}, tenant: {self.tenant})")
                return created
            except Exception as e:
                error_str = str(e)
                if "already exists" in error_str or "409" in error_str:
                    # Collection was created by another process - try to get it again
                    logger.info(f"Collection already exists (attempt {attempt + 1}/{max_retries}), retrying fetch: {collection_name}")
                    if attempt < max_retries - 1:
                        # Wait a bit to avoid race condition, then retry the whole process
                        await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        # Final attempt - try to get the collection one more time
                        existing = await self.get_collection(collection_name)
                        if existing:
                            logger.info(f"Collection retrieved on final attempt: {collection_name}")
                            return existing
                        # If we still can't get it, something's wrong
                        logger.error(f"Failed to retrieve collection after multiple attempts: {collection_name}")
                        raise
                else:
                    # Different error - log and re-raise
                    logger.warning(f"Collection creation failed: {collection_name} (tenant: {self.tenant}, error: {error_str}) - Check if Chroma server supports tenant endpoints or requires authentication")
                    raise
        
        # Should not reach here, but just in case
        raise Exception(f"Failed to get or create collection after {max_retries} attempts: {collection_name}")

    async def get_collection(self, name: Optional[str]) -> Optional[Dict[str, Any]]:
        """Return collection info if exists; otherwise None."""
        if not name:
            raise ValueError("get_collection requires a collection name")

        if self.use_v1_mode:
            # For v1 API, try to get collection directly by name in path
            url = f"{self._get_collections_url()}/{name}"
            result = await self._get_json(url, allow_404=True)
            if isinstance(result, dict) and result.get("name") == name:
                return result
            
            # If direct access fails, fall back to listing all and filtering
            url = self._get_collections_url()
            result = await self._get_json(url, allow_404=True)
            if isinstance(result, list):
                for c in result:
                    if isinstance(c, dict) and c.get("name") == name:
                        return c
            return None
        else:
            # v2 mode logic (original)
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

    async def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections. Returns list of collection info dicts."""
        url = self._v2_url("collections")
        result = await self._get_json(url)
        
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "collections" in result:
            return result.get("collections", [])
        else:
            logger.warning(f"Unexpected list_collections response: {result}")
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Return health result with collection readiness."""
        health: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": __import__("time").time(),
            "checks": {}
        }
        try:
            # 1) Base healthcheck (use appropriate version)
            if self.use_v1_mode:
                ok = await self._healthcheck_v1()
                health["checks"]["v1_healthcheck"] = {"status": "pass" if ok else "fail"}
            else:
                ok = await self._healthcheck_v2()
                health["checks"]["v2_healthcheck"] = {"status": "pass" if ok else "fail"}
            
            if not ok:
                health["status"] = "unhealthy"

            # 2) Tenant readiness (v2 only)
            if not self.use_v1_mode:
                try:
                    tenant_url = f"{self.base_url}/api/v2/tenants/{self.tenant}"
                    _ = await self._get_json(tenant_url)
                    health["checks"]["tenant"] = {"status": "pass", "tenant": self.tenant}
                except Exception as te:
                    health["checks"]["tenant"] = {"status": "fail", "tenant": self.tenant, "error": str(te)}
                    health["status"] = "unhealthy"

                # 3) Database readiness (v2 only)
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

    async def add_chunks(self, chunks, collection_name: Optional[str] = None) -> bool:
        """
        Add chunks to ChromaDB collection.
        Expected chunks format: list of EnhancedChunk objects or similar with 
        attributes: id, content, metadata, embeddings
        """
        try:
            collection_name = collection_name or self.collection_name
            if not collection_name:
                logger.error("No collection name provided for add_chunks")
                return False
                
            # Ensure collection exists
            await self.get_or_create_collection(collection_name)
            
            # Prepare data for ChromaDB
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            for chunk in chunks:
                # Handle both EnhancedChunk and direct CodeChunk objects
                if hasattr(chunk, 'chunk'):
                    # EnhancedChunk - extract data from nested chunk
                    code_chunk = chunk.chunk
                    ids.append(code_chunk.id)
                    documents.append(code_chunk.content)
                    
                    # Build metadata from both EnhancedChunk and CodeChunk
                    metadata = {}
                    if hasattr(code_chunk, 'language'):
                        metadata['language'] = str(code_chunk.language)
                    if hasattr(code_chunk, 'chunk_type'):
                        metadata['chunk_type'] = code_chunk.chunk_type
                    if hasattr(code_chunk, 'name') and code_chunk.name:
                        metadata['name'] = code_chunk.name
                    if hasattr(code_chunk, 'start_line'):
                        metadata['start_line'] = code_chunk.start_line
                    if hasattr(code_chunk, 'end_line'):
                        metadata['end_line'] = code_chunk.end_line
                    
                    # Add EnhancedChunk metadata
                    if hasattr(chunk, 'business_domain') and chunk.business_domain:
                        metadata['business_domain'] = chunk.business_domain
                    if hasattr(chunk, 'importance_score'):
                        metadata['importance_score'] = chunk.importance_score
                    
                    metadatas.append(metadata)
                    
                    # Handle embeddings from EnhancedChunk
                    if hasattr(chunk, 'embeddings') and chunk.embeddings:
                        embeddings.append(chunk.embeddings)
                    elif hasattr(chunk, 'embedding') and chunk.embedding:
                        embeddings.append(chunk.embedding)
                    elif hasattr(code_chunk, 'embeddings') and code_chunk.embeddings:
                        embeddings.append(code_chunk.embeddings)
                    elif hasattr(code_chunk, 'embedding') and code_chunk.embedding:
                        embeddings.append(code_chunk.embedding)
                else:
                    # Direct CodeChunk or other chunk format
                    ids.append(getattr(chunk, 'id', str(hash(chunk))))
                    documents.append(getattr(chunk, 'content', str(chunk)))
                    
                    # Handle metadata
                    metadata = getattr(chunk, 'metadata', {})
                    if hasattr(chunk, 'file_path'):
                        metadata['file_path'] = str(chunk.file_path)
                    if hasattr(chunk, 'language'):
                        metadata['language'] = str(chunk.language)
                    if hasattr(chunk, 'chunk_type'):
                        metadata['chunk_type'] = chunk.chunk_type
                    metadatas.append(metadata)
                    
                    # Handle embeddings if available
                    if hasattr(chunk, 'embeddings') and chunk.embeddings:
                        embeddings.append(chunk.embeddings)
                    elif hasattr(chunk, 'embedding') and chunk.embedding:
                        embeddings.append(chunk.embedding)
            
            # Get collection info to get the ID
            collection_info = await self.get_or_create_collection(collection_name)
            collection_id = collection_info.get('id')
            if not collection_id:
                logger.error(f"Could not get collection ID for {collection_name}")
                return False
            
            # Add to ChromaDB collection using collection ID in batches to avoid timeouts
            url = f"{self._get_collections_url()}/{collection_id}/add"
            batch_size = 500  # Process chunks in smaller batches to avoid timeouts
            total_chunks = len(documents)
            
            logger.info(f"Adding {total_chunks} chunks to collection {collection_name} in batches of {batch_size}")
            logger.info(f"ChromaDB Client Config: use_v1_mode={self.use_v1_mode}, tenant={self.tenant}, database={self.database}")
            logger.info(f"Collection URL: {url}")
            logger.info(f"Collection ID: {collection_id}")
            
            # Process chunks in batches
            for i in range(0, total_chunks, batch_size):
                end_idx = min(i + batch_size, total_chunks)
                batch_documents = documents[i:end_idx]
                batch_metadatas = metadatas[i:end_idx]
                batch_ids = ids[i:end_idx]
                
                payload = {
                    "documents": batch_documents,
                    "metadatas": batch_metadatas,
                    "ids": batch_ids
                }
                
                # Only include embeddings if we have them
                if embeddings and len(embeddings) == len(documents):
                    batch_embeddings = embeddings[i:end_idx]
                    payload["embeddings"] = batch_embeddings
                
                # Use longer timeout for storage operations
                try:
                    await self._post_json(url, payload, timeout_override=120.0)  # 2-minute timeout for storage
                    logger.info(f"Successfully added batch {i//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size} ({end_idx - i} chunks)")
                except Exception as e:
                    logger.error(f"Failed to add batch {i//batch_size + 1} (chunks {i}-{end_idx}): {e}")
                    raise  # Re-raise to fail the entire operation
            
            logger.info(f"Successfully added all {total_chunks} chunks to collection {collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"🚨 CRITICAL: Failed to add chunks to ChromaDB - Exception: {e}")
            logger.error(f"🚨 Exception type: {type(e)}")
            logger.error(f"🚨 Exception args: {e.args}")
            logger.error(f"🚨 Chunks count: {len(chunks)}")
            logger.error(f"🚨 Collection name: {collection_name}")
            if chunks:
                sample_chunk = chunks[0]
                logger.error(f"🚨 Sample chunk type: {type(sample_chunk)}")
                logger.error(f"🚨 Sample chunk attributes: {[attr for attr in dir(sample_chunk) if not attr.startswith('_')]}")
                if hasattr(sample_chunk, 'chunk'):
                    logger.error(f"🚨 Nested chunk attributes: {[attr for attr in dir(sample_chunk.chunk) if not attr.startswith('_')]}")
            logger.error(f"🚨 Full traceback:", exc_info=True)
            return False

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

    def _get_collections_url(self) -> str:
        """Get the correct collections URL based on API mode."""
        if self.use_v1_mode:
            # Use v1 collections endpoint
            url = f"{self.base_url}/api/v1/collections"
            logger.debug(f"Building v1 collections URL: {url}")
            return url
        else:
            url = f"{self.base_url}/api/v2/tenants/{self.tenant}/databases/{self.database}/collections"
            logger.debug(f"Building v2 tenant collections URL: {url} (tenant: {self.tenant}, database: {self.database})")
            return url

    def _v2_url(self, resource: str) -> str:
        """
        Build an endpoint using the appropriate API version structure.
        """
        if resource == "collections":
            return self._get_collections_url()
        else:
            # For other resources like healthcheck, use the appropriate API version
            if self.use_v1_mode:
                url = f"{self.base_url}/api/v1/{resource}"
                logger.debug(f"Building v1 URL: {url} (resource: {resource})")
            else:
                url = f"{self.base_url}/api/v2/{resource}"
                logger.debug(f"Building v2 URL: {url} (resource: {resource})")
            return url

    async def _healthcheck_v2(self) -> bool:
        url = f"{self.base_url}/api/v2/healthcheck"
        try:
            result = await self._get_json(url)
            # Many servers return {"status":"ok"}; accept any 200 JSON as OK.
            return isinstance(result, dict)
        except Exception:
            return False
    
    async def _healthcheck_v1(self) -> bool:
        url = f"{self.base_url}/api/v1/heartbeat"
        try:
            result = await self._get_json(url)
            # v1 heartbeat returns {"nanosecond heartbeat": timestamp}
            return isinstance(result, dict) and "nanosecond heartbeat" in result
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

    async def _post_json(self, url: str, payload: Dict[str, Any], timeout_override: Optional[float] = None) -> Any:
        if self._session is None:
            raise RuntimeError("Client not initialized")
        
        # Use custom timeout if provided, otherwise use default session timeout
        timeout = aiohttp.ClientTimeout(total=timeout_override) if timeout_override else None
        
        async with self._session.post(url, headers=self._headers, data=json.dumps(payload), timeout=timeout) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise ChromaV2Error(f"POST {url} failed: {resp.status} {text}")
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" in ctype:
                return await resp.json()
            return await resp.text()