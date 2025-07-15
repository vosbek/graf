"""
Logging middleware for request/response logging and performance monitoring.
"""

import time
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import json


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    def __init__(self, app, logger_name: str = "api"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        # Log request start
        start_time = time.time()
        
        # Extract request details
        request_details = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "timestamp": time.time()
        }
        
        # Log request body for non-GET requests (be careful with sensitive data)
        if request.method != "GET":
            try:
                # Read body if available
                body = await request.body()
                if body and len(body) < 10000:  # Limit body size in logs
                    request_details["body_size"] = len(body)
                    # Don't log actual body content for security
                else:
                    request_details["body_size"] = len(body) if body else 0
            except Exception:
                request_details["body_size"] = 0
        
        # Log request
        self.logger.info(f"Request started", extra=request_details)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log response
            response_details = {
                "request_id": request_id,
                "status_code": response.status_code,
                "processing_time": processing_time,
                "response_size": len(response.body) if hasattr(response, 'body') else 0,
                "timestamp": time.time()
            }
            
            # Log response
            log_level = logging.INFO
            if response.status_code >= 400:
                log_level = logging.WARNING
            if response.status_code >= 500:
                log_level = logging.ERROR
            
            self.logger.log(log_level, f"Request completed", extra=response_details)
            
            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"
            
            return response
            
        except Exception as e:
            # Log error
            processing_time = time.time() - start_time
            
            error_details = {
                "request_id": request_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "processing_time": processing_time,
                "timestamp": time.time()
            }
            
            self.logger.error(f"Request failed", extra=error_details)
            
            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "request_id": request_id,
                    "timestamp": time.time()
                },
                headers={"X-Request-ID": request_id}
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client address
        if request.client:
            return request.client.host
        
        return "unknown"


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for performance monitoring and metrics collection."""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger("performance")
        
        # Performance metrics
        self.request_count = 0
        self.total_processing_time = 0.0
        self.slow_request_threshold = 5.0  # seconds
        
        # Endpoint metrics
        self.endpoint_metrics = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance."""
        start_time = time.time()
        
        # Get endpoint key
        endpoint_key = f"{request.method}:{request.url.path}"
        
        # Initialize endpoint metrics if not exists
        if endpoint_key not in self.endpoint_metrics:
            self.endpoint_metrics[endpoint_key] = {
                "count": 0,
                "total_time": 0.0,
                "min_time": float('inf'),
                "max_time": 0.0,
                "error_count": 0
            }
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate metrics
            processing_time = time.time() - start_time
            
            # Update global metrics
            self.request_count += 1
            self.total_processing_time += processing_time
            
            # Update endpoint metrics
            endpoint_stats = self.endpoint_metrics[endpoint_key]
            endpoint_stats["count"] += 1
            endpoint_stats["total_time"] += processing_time
            endpoint_stats["min_time"] = min(endpoint_stats["min_time"], processing_time)
            endpoint_stats["max_time"] = max(endpoint_stats["max_time"], processing_time)
            
            if response.status_code >= 400:
                endpoint_stats["error_count"] += 1
            
            # Log slow requests
            if processing_time > self.slow_request_threshold:
                slow_request_details = {
                    "endpoint": endpoint_key,
                    "processing_time": processing_time,
                    "threshold": self.slow_request_threshold,
                    "request_id": getattr(request.state, 'request_id', 'unknown')
                }
                self.logger.warning("Slow request detected", extra=slow_request_details)
            
            return response
            
        except Exception as e:
            # Update error metrics
            processing_time = time.time() - start_time
            
            endpoint_stats = self.endpoint_metrics[endpoint_key]
            endpoint_stats["error_count"] += 1
            
            raise e
    
    def get_metrics(self) -> dict:
        """Get performance metrics."""
        avg_processing_time = self.total_processing_time / max(self.request_count, 1)
        
        # Calculate endpoint averages
        endpoint_averages = {}
        for endpoint, stats in self.endpoint_metrics.items():
            endpoint_averages[endpoint] = {
                "count": stats["count"],
                "avg_time": stats["total_time"] / max(stats["count"], 1),
                "min_time": stats["min_time"] if stats["min_time"] != float('inf') else 0,
                "max_time": stats["max_time"],
                "error_rate": stats["error_count"] / max(stats["count"], 1),
                "error_count": stats["error_count"]
            }
        
        return {
            "global_metrics": {
                "total_requests": self.request_count,
                "avg_processing_time": avg_processing_time,
                "total_processing_time": self.total_processing_time
            },
            "endpoint_metrics": endpoint_averages,
            "timestamp": time.time()
        }
    
    def reset_metrics(self):
        """Reset all metrics."""
        self.request_count = 0
        self.total_processing_time = 0.0
        self.endpoint_metrics = {}


class SecurityLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for security-related logging."""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger("security")
        
        # Security patterns to watch for
        self.suspicious_patterns = [
            r'(?i)(union|select|insert|update|delete|drop|create|alter)\s+',
            r'(?i)<script[^>]*>.*?</script>',
            r'(?i)javascript:',
            r'(?i)on\w+\s*=',
            r'\.\./',
            r'%2e%2e%2f',
            r'(?i)(exec|eval|system|cmd)',
        ]
        
        # Rate limiting tracking
        self.client_requests = {}
        self.rate_limit_window = 60  # seconds
        self.rate_limit_max = 100  # requests per window
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor security-related events."""
        client_ip = self._get_client_ip(request)
        
        # Check for suspicious patterns
        await self._check_suspicious_patterns(request)
        
        # Check rate limiting
        await self._check_rate_limiting(request, client_ip)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Log security events
            if response.status_code == 401:
                self._log_security_event("authentication_failed", request)
            elif response.status_code == 403:
                self._log_security_event("authorization_failed", request)
            elif response.status_code == 429:
                self._log_security_event("rate_limit_exceeded", request)
            
            return response
            
        except Exception as e:
            self._log_security_event("request_error", request, {"error": str(e)})
            raise
    
    async def _check_suspicious_patterns(self, request: Request):
        """Check for suspicious patterns in request."""
        # Check URL path
        for pattern in self.suspicious_patterns:
            if re.search(pattern, request.url.path):
                self._log_security_event("suspicious_url_pattern", request, {
                    "pattern": pattern,
                    "url": str(request.url)
                })
        
        # Check query parameters
        for key, value in request.query_params.items():
            for pattern in self.suspicious_patterns:
                if re.search(pattern, value):
                    self._log_security_event("suspicious_query_parameter", request, {
                        "pattern": pattern,
                        "parameter": key,
                        "value": value[:100]  # Truncate value
                    })
    
    async def _check_rate_limiting(self, request: Request, client_ip: str):
        """Check rate limiting for client."""
        current_time = time.time()
        
        # Clean old entries
        self.client_requests = {
            ip: requests for ip, requests in self.client_requests.items()
            if any(req_time > current_time - self.rate_limit_window for req_time in requests)
        }
        
        # Update client requests
        if client_ip not in self.client_requests:
            self.client_requests[client_ip] = []
        
        # Filter requests within window
        self.client_requests[client_ip] = [
            req_time for req_time in self.client_requests[client_ip]
            if req_time > current_time - self.rate_limit_window
        ]
        
        # Add current request
        self.client_requests[client_ip].append(current_time)
        
        # Check if rate limit exceeded
        if len(self.client_requests[client_ip]) > self.rate_limit_max:
            self._log_security_event("rate_limit_exceeded", request, {
                "client_ip": client_ip,
                "request_count": len(self.client_requests[client_ip]),
                "limit": self.rate_limit_max,
                "window": self.rate_limit_window
            })
    
    def _log_security_event(self, event_type: str, request: Request, additional_data: dict = None):
        """Log security event."""
        security_event = {
            "event_type": event_type,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "timestamp": time.time(),
            "request_id": getattr(request.state, 'request_id', 'unknown')
        }
        
        if additional_data:
            security_event.update(additional_data)
        
        self.logger.warning(f"Security event: {event_type}", extra=security_event)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to client address
        if request.client:
            return request.client.host
        
        return "unknown"


# Global middleware instances
performance_middleware = None
security_middleware = None


def get_performance_metrics() -> dict:
    """Get performance metrics from middleware."""
    global performance_middleware
    if performance_middleware:
        return performance_middleware.get_metrics()
    return {}


def reset_performance_metrics():
    """Reset performance metrics."""
    global performance_middleware
    if performance_middleware:
        performance_middleware.reset_metrics()


def initialize_middleware_instances(app):
    """Initialize global middleware instances."""
    global performance_middleware, security_middleware
    
    # This would be called from the main application
    for middleware in app.middleware:
        if isinstance(middleware, PerformanceMonitoringMiddleware):
            performance_middleware = middleware
        elif isinstance(middleware, SecurityLoggingMiddleware):
            security_middleware = middleware