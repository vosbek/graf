"""
Authentication middleware for API security.
"""

import time
import jwt
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ...config.settings import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT-based authentication."""
    
    def __init__(self, app):
        super().__init__(app)
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        
        # Public endpoints that don't require authentication
        self.public_endpoints = {
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/api/v1/health",
            "/api/v1/health/",
            "/api/v1/health/live",
            "/api/v1/health/ready",
            "/api/v1/health/version",
            "/api/v1/health/metrics"
        }
        
        # Admin endpoints that require special permissions
        self.admin_endpoints = {
            "/api/v1/admin",
            "/api/v1/admin/",
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process authentication for requests."""
        # Skip authentication for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Check for authentication token
        token = self._extract_token(request)
        
        if not token:
            return self._unauthorized_response("Missing authentication token")
        
        # Verify token
        try:
            payload = self._verify_token(token)
            
            # Add user info to request state
            request.state.user_id = payload.get("user_id")
            request.state.username = payload.get("username")
            request.state.roles = payload.get("roles", [])
            request.state.permissions = payload.get("permissions", [])
            
            # Check admin permissions for admin endpoints
            if self._is_admin_endpoint(request.url.path):
                if not self._has_admin_permission(payload):
                    return self._forbidden_response("Insufficient permissions")
            
            # Process request
            response = await call_next(request)
            
            return response
            
        except jwt.ExpiredSignatureError:
            return self._unauthorized_response("Token has expired")
        except jwt.InvalidTokenError:
            return self._unauthorized_response("Invalid token")
        except Exception as e:
            return self._unauthorized_response(f"Authentication error: {str(e)}")
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public."""
        # Exact match
        if path in self.public_endpoints:
            return True
        
        # Prefix match for health endpoints
        if path.startswith("/api/v1/health"):
            return True
        
        # Static file endpoints
        if path.startswith("/static/"):
            return True
        
        return False
    
    def _is_admin_endpoint(self, path: str) -> bool:
        """Check if endpoint requires admin permissions."""
        return path.startswith("/api/v1/admin")
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract JWT token from request."""
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        
        # Check query parameter (less secure, for development only)
        if not settings.is_production():
            token = request.query_params.get("token")
            if token:
                return token
        
        # Check cookie
        token = request.cookies.get("access_token")
        if token:
            return token
        
        return None
    
    def _verify_token(self, token: str) -> dict:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Check expiration
            if payload.get("exp", 0) < time.time():
                raise jwt.ExpiredSignatureError("Token has expired")
            
            return payload
            
        except jwt.InvalidTokenError:
            raise
        except Exception as e:
            raise jwt.InvalidTokenError(f"Token verification failed: {str(e)}")
    
    def _has_admin_permission(self, payload: dict) -> bool:
        """Check if user has admin permissions."""
        roles = payload.get("roles", [])
        permissions = payload.get("permissions", [])
        
        # Check for admin role
        if "admin" in roles:
            return True
        
        # Check for admin permissions
        if "admin:read" in permissions or "admin:write" in permissions:
            return True
        
        return False
    
    def _unauthorized_response(self, message: str) -> JSONResponse:
        """Return unauthorized response."""
        return JSONResponse(
            status_code=401,
            content={
                "error": "Unauthorized",
                "message": message,
                "timestamp": time.time()
            },
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    def _forbidden_response(self, message: str) -> JSONResponse:
        """Return forbidden response."""
        return JSONResponse(
            status_code=403,
            content={
                "error": "Forbidden",
                "message": message,
                "timestamp": time.time()
            }
        )


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware for API key-based authentication."""
    
    def __init__(self, app):
        super().__init__(app)
        
        # API keys would be stored in a database or secure storage
        # For demo purposes, using in-memory storage
        self.api_keys = {
            "admin_key_123": {
                "name": "Admin Key",
                "roles": ["admin"],
                "permissions": ["admin:read", "admin:write", "query:read", "index:write"],
                "rate_limit": 1000,
                "created_at": time.time()
            },
            "query_key_456": {
                "name": "Query Key",
                "roles": ["user"],
                "permissions": ["query:read"],
                "rate_limit": 100,
                "created_at": time.time()
            }
        }
        
        # Rate limiting tracking
        self.api_key_usage = {}
        self.rate_limit_window = 3600  # 1 hour
    
    async def dispatch(self, request: Request, call_next):
        """Process API key authentication for requests."""
        # Skip for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Extract API key
        api_key = self._extract_api_key(request)
        
        if not api_key:
            return self._unauthorized_response("Missing API key")
        
        # Validate API key
        key_info = self.api_keys.get(api_key)
        if not key_info:
            return self._unauthorized_response("Invalid API key")
        
        # Check rate limiting
        if not self._check_rate_limit(api_key, key_info):
            return self._rate_limit_response("API key rate limit exceeded")
        
        # Add API key info to request state
        request.state.api_key = api_key
        request.state.api_key_name = key_info["name"]
        request.state.roles = key_info["roles"]
        request.state.permissions = key_info["permissions"]
        
        # Update usage tracking
        self._update_usage(api_key)
        
        # Process request
        response = await call_next(request)
        
        return response
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public."""
        public_endpoints = {
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/api/v1/health",
            "/api/v1/health/",
            "/api/v1/health/live",
            "/api/v1/health/ready"
        }
        
        return path in public_endpoints or path.startswith("/api/v1/health")
    
    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request."""
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key
        
        # Check query parameter
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key
        
        return None
    
    def _check_rate_limit(self, api_key: str, key_info: dict) -> bool:
        """Check if API key is within rate limit."""
        current_time = time.time()
        rate_limit = key_info["rate_limit"]
        
        # Initialize usage tracking
        if api_key not in self.api_key_usage:
            self.api_key_usage[api_key] = []
        
        # Clean old entries
        self.api_key_usage[api_key] = [
            req_time for req_time in self.api_key_usage[api_key]
            if req_time > current_time - self.rate_limit_window
        ]
        
        # Check if within limit
        return len(self.api_key_usage[api_key]) < rate_limit
    
    def _update_usage(self, api_key: str):
        """Update API key usage tracking."""
        if api_key not in self.api_key_usage:
            self.api_key_usage[api_key] = []
        
        self.api_key_usage[api_key].append(time.time())
    
    def _unauthorized_response(self, message: str) -> JSONResponse:
        """Return unauthorized response."""
        return JSONResponse(
            status_code=401,
            content={
                "error": "Unauthorized",
                "message": message,
                "timestamp": time.time()
            }
        )
    
    def _rate_limit_response(self, message: str) -> JSONResponse:
        """Return rate limit response."""
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate Limit Exceeded",
                "message": message,
                "timestamp": time.time()
            },
            headers={"Retry-After": str(self.rate_limit_window)}
        )


def create_jwt_token(user_id: str, username: str, roles: list, permissions: list) -> str:
    """Create JWT token for user."""
    payload = {
        "user_id": user_id,
        "username": username,
        "roles": roles,
        "permissions": permissions,
        "iat": time.time(),
        "exp": time.time() + (settings.jwt_expiration_hours * 3600)
    }
    
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )


def verify_jwt_token(token: str) -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")


def get_current_user(request: Request) -> dict:
    """Get current user from request state."""
    return {
        "user_id": getattr(request.state, "user_id", None),
        "username": getattr(request.state, "username", None),
        "roles": getattr(request.state, "roles", []),
        "permissions": getattr(request.state, "permissions", [])
    }


def require_permission(permission: str):
    """Decorator to require specific permission."""
    def decorator(func):
        def wrapper(request: Request, *args, **kwargs):
            user_permissions = getattr(request.state, "permissions", [])
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Required permission: {permission}"
                )
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_role(role: str):
    """Decorator to require specific role."""
    def decorator(func):
        def wrapper(request: Request, *args, **kwargs):
            user_roles = getattr(request.state, "roles", [])
            if role not in user_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Required role: {role}"
                )
            return func(request, *args, **kwargs)
        return wrapper
    return decorator