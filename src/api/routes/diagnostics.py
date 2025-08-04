"""
Diagnostic and troubleshooting API endpoints.
Note: This module defines an APIRouter named 'router'. Ensure it is imported and included by the FastAPI app.
"""

import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from ...services.diagnostic_service import DiagnosticService
from ...services.problem_detector import ProblemDetector
from ...dependencies import (
    get_chroma_client, get_neo4j_client, get_repository_processor, 
    get_embedding_client
)

router = APIRouter()

# Global diagnostic service instance
diagnostic_service = DiagnosticService()
problem_detector = ProblemDetector(diagnostic_service)


class DiagnosticRequest(BaseModel):
    """Request model for diagnostic operations."""
    include_performance_history: bool = False
    export_format: str = "json"


class AutoFixRequest(BaseModel):
    """Request model for auto-fix operations."""
    issue_ids: list[str]
    confirm: bool = False


@router.get("/system")
async def get_system_diagnostics(
    request: Request,
    include_history: bool = Query(False, description="Include performance history"),
    timeout: int = Query(30, description="Timeout in seconds")
):
    """
    Canonical System Status endpoint consumed by the frontend.
    Aggregates /api/v1/health/ready and /api/v1/health/detailed to produce a single source of truth.
    """
    try:
        # Fetch readiness and detailed health in parallel with timeouts
        from ..routes.health import readiness_check, detailed_health_check  # local import to avoid circulars at import time

        async def _readiness():
            return await asyncio.wait_for(readiness_check(request), timeout=timeout)

        async def _detailed():
            return await asyncio.wait_for(detailed_health_check(request), timeout=timeout)

        ready_task = asyncio.create_task(_readiness())
        detailed_task = asyncio.create_task(_detailed())
        readiness = await ready_task
        detailed = await detailed_task

        # Normalize/compose a unified payload
        status = readiness.get("status", "not_ready")
        checks = readiness.get("checks", {})
        health_score = readiness.get("health_score", 0)
        validation_time = readiness.get("validation_time", 0.0)

        components = {
            "chromadb": {
                "status": checks.get("chromadb", {}).get("status"),
                "ready": checks.get("chromadb", {}).get("ready"),
                "details": checks.get("chromadb")
            },
            "neo4j": {
                "status": checks.get("neo4j", {}).get("status"),
                "ready": checks.get("neo4j", {}).get("ready"),
                "details": checks.get("neo4j")
            },
            "repository_processor": {
                "status": checks.get("processor", {}).get("status"),
                "ready": checks.get("processor", {}).get("ready"),
                "details": checks.get("processor")
            },
            "embedding_system": {
                "status": checks.get("embedding_system", {}).get("status"),
                "ready": checks.get("embedding_system", {}).get("ready"),
                "details": checks.get("embedding_system")
            }
        }

        response_data = {
            "status": status,
            "health_score": health_score,
            "timestamp": readiness.get("timestamp"),
            "validation_time": validation_time,
            "components": components,
            "system_info": getattr(detailed, "system_info", None) or getattr(detailed, "dict", lambda: {})().get("system_info") or getattr(detailed, "model_dump", lambda: {})().get("system_info") or {},
            "detailed": detailed if isinstance(detailed, dict) else getattr(detailed, "dict", lambda: detailed)(),
        }

        # Include performance history if requested
        if include_history:
            try:
                response_data['performance_history'] = await diagnostic_service.get_performance_history()
            except Exception:
                response_data['performance_history'] = []

        # Derive concise recommendations from readiness troubleshooting if present
        if 'troubleshooting' in readiness:
            response_data['troubleshooting'] = readiness['troubleshooting']

        return response_data

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail={
                "error": "Diagnostic timeout",
                "message": f"System diagnostics timed out after {timeout} seconds"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Diagnostic failed",
                "message": str(e)
            }
        )


@router.get("/issues")
async def get_current_issues(
    request: Request,
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, error, critical"),
    component: Optional[str] = Query(None, description="Filter by component")
):
    """
    Issues list derived from readiness and detailed health for UI consumption.
    """
    try:
        from ..routes.health import readiness_check, detailed_health_check

        readiness = await readiness_check(request)
        detailed = await detailed_health_check(request)

        checks = readiness.get("checks", {})
        issues = []

        def add_issue(name: str, check: Dict[str, Any]):
            status = check.get("status")
            ready = check.get("ready", False)
            if ready:
                return
            issue = {
                "id": f"{name}_unready",
                "component": name,
                "level": "error" if status in ("unhealthy", "timeout") else "warning",
                "message": f"{name} not ready (status={status})",
                "details": check,
                "remediation": check.get("troubleshooting") or "Check component logs and configuration"
            }
            issues.append(issue)

        for name in ("chromadb", "neo4j", "processor", "embedding_system"):
            if name in checks:
                add_issue(name, checks[name])

        # Optional: include detailed health errors if present
        if isinstance(detailed, dict) and detailed.get("status") == "unhealthy":
            issues.append({
                "id": "overall_unhealthy",
                "component": "system",
                "level": "warning",
                "message": "Detailed health reports unhealthy",
                "details": detailed
            })

        # Apply filters
        if severity:
            issues = [i for i in issues if i["level"] == severity.lower()]
        if component:
            issues = [i for i in issues if i["component"] == component]

        return {
            "issues": issues,
            "total_count": len(issues),
            "filtered_count": len(issues),
            "filters": {"severity": severity, "component": component}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get issues: {str(e)}")


@router.get("/troubleshooting/{issue_id}")
async def get_troubleshooting_guide(issue_id: str):
    """
    Get detailed troubleshooting guide for a specific issue.
    
    Returns step-by-step remediation instructions and additional context.
    """
    try:
        # Get remediation info from diagnostic service
        remediation_db = diagnostic_service.remediation_database
        
        if issue_id not in remediation_db:
            raise HTTPException(
                status_code=404,
                detail=f"Troubleshooting guide not found for issue: {issue_id}"
            )
        
        guide = remediation_db[issue_id]
        
        return {
            "issue_id": issue_id,
            "title": guide["title"],
            "description": guide["description"],
            "component_type": guide["component_type"].value,
            "remediation_steps": guide["remediation_steps"],
            "auto_fixable": guide["auto_fixable"],
            "additional_resources": [
                "Check application logs for more details",
                "Monitor system resources during troubleshooting",
                "Contact support if issue persists after following steps"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get troubleshooting guide: {str(e)}"
        )


@router.get("/health-report")
async def get_health_report(
    request: Request,
    format: str = Query("json", description="Report format: json or text")
):
    """
    Get comprehensive health report.
    
    Returns a detailed health report suitable for sharing with support.
    """
    try:
        # Get clients
        clients = await _get_clients_with_timeout(request, 20)
        
        # Run diagnostics
        diagnostics = await diagnostic_service.run_comprehensive_diagnostics(
            chroma_client=clients.get('chroma_client'),
            neo4j_client=clients.get('neo4j_client'),
            processor=clients.get('processor'),
            embedding_client=clients.get('embedding_client')
        )
        
        if format.lower() == "text":
            report_text = await diagnostic_service.export_diagnostic_data(diagnostics, "text")
            return PlainTextResponse(
                content=report_text,
                headers={"Content-Disposition": "attachment; filename=health_report.txt"}
            )
        else:
            return {
                "report": diagnostics.to_dict(),
                "export_timestamp": diagnostics.timestamp.isoformat(),
                "format": "json"
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate health report: {str(e)}"
        )


@router.get("/performance-history")
async def get_performance_history():
    """
    Get performance history for trending analysis.
    
    Returns historical performance metrics and health scores.
    """
    try:
        history = await diagnostic_service.get_performance_history()
        
        return {
            "history": history,
            "total_entries": len(history),
            "time_range": {
                "oldest": history[0]["timestamp"] if history else None,
                "newest": history[-1]["timestamp"] if history else None
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get performance history: {str(e)}"
        )


@router.get("/auto-fixes")
async def get_auto_fix_suggestions(request: Request):
    """
    Get suggestions for automatic fixes.
    
    Returns a list of issues that can be automatically resolved.
    """
    try:
        # Get clients
        clients = await _get_clients_with_timeout(request, 15)
        
        # Run problem detection
        problems = await problem_detector.detect_problems(
            chroma_client=clients.get('chroma_client'),
            neo4j_client=clients.get('neo4j_client'),
            processor=clients.get('processor'),
            embedding_client=clients.get('embedding_client')
        )
        
        # Get auto-fix suggestions
        auto_fixes = await problem_detector.get_auto_fix_suggestions(problems)
        
        return {
            "auto_fixes": [
                {
                    "problem_id": fix.problem_id,
                    "title": fix.title,
                    "description": fix.description,
                    "fix_command": fix.fix_command,
                    "risk_level": fix.risk_level,
                    "estimated_time": fix.estimated_time,
                    "prerequisites": fix.prerequisites,
                    "success_criteria": fix.success_criteria,
                    "rollback_command": fix.rollback_command
                }
                for fix in auto_fixes
            ],
            "total_fixable_issues": len(auto_fixes),
            "warning": "Auto-fixes should be reviewed before execution"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get auto-fix suggestions: {str(e)}"
        )


@router.post("/auto-fix")
async def execute_auto_fix(fix_request: AutoFixRequest):
    """
    Execute automatic fixes for specified issues.
    
    WARNING: This endpoint can modify system state. Use with caution.
    """
    if not fix_request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Auto-fix execution requires explicit confirmation"
        )
    
    # For now, return not implemented
    # In a production system, this would execute the actual fixes
    return {
        "status": "not_implemented",
        "message": "Auto-fix execution is not yet implemented",
        "requested_fixes": fix_request.issue_ids,
        "recommendation": "Please execute fixes manually following the troubleshooting guides"
    }


@router.get("/component-status/{component_name}")
async def get_component_status(component_name: str, request: Request):
    """
    Get detailed status for a specific component.
    
    Returns health information and diagnostics for the specified component.
    """
    try:
        # Get clients
        clients = await _get_clients_with_timeout(request, 10)
        
        # Run diagnostics
        diagnostics = await diagnostic_service.run_comprehensive_diagnostics(
            chroma_client=clients.get('chroma_client'),
            neo4j_client=clients.get('neo4j_client'),
            processor=clients.get('processor'),
            embedding_client=clients.get('embedding_client')
        )
        
        # Find component status
        component_status = diagnostics.component_status.get(component_name)
        if not component_status:
            raise HTTPException(
                status_code=404,
                detail=f"Component not found: {component_name}"
            )
        
        # Find component issues
        component_issues = [
            issue.to_dict() for issue in diagnostics.issues 
            if issue.component == component_name
        ]
        
        return {
            "component": component_name,
            "status": component_status,
            "issues": component_issues,
            "issue_count": len(component_issues),
            "last_checked": diagnostics.timestamp.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get component status: {str(e)}"
        )


@router.get("/recommendations")
async def get_system_recommendations(request: Request):
    """
    Recommendations derived from readiness failed components and performance signals.
    """
    try:
        from ..routes.health import readiness_check, detailed_health_check

        readiness = await readiness_check(request)
        detailed = await detailed_health_check(request)

        checks = readiness.get("checks", {})
        recs = []

        # Component-specific recommendations
        if "chromadb" in checks and not checks["chromadb"].get("ready", False):
            recs.append("Check ChromaDB service and /api/v2/healthcheck; verify CHROMADB_HOST/PORT and container logs.")
        if "neo4j" in checks and not checks["neo4j"].get("ready", False):
            recs.append("Verify Neo4j connectivity over bolt; confirm credentials and monitor pod logs for errors.")
        if "processor" in checks and not checks["processor"].get("ready", False):
            recs.append("Ensure repository processor dependencies are healthy; check processor logs for exceptions.")
        if "embedding_system" in checks and not checks["embedding_system"].get("ready", True):
            recs.append("Embedding system is optional; initialize if advanced features are required or keep disabled.")

        # Performance hint from detailed metrics if available
        try:
            system_info = detailed.get("system_info", {}) if isinstance(detailed, dict) else {}
            if system_info.get("cpu_usage", 0) > 85:
                recs.append("High CPU usage detected; consider reducing concurrency or increasing resources.")
            if system_info.get("memory_usage", 0) > 85:
                recs.append("High memory usage detected; consider increasing memory or reducing model size.")
        except Exception:
            pass

        # Deduplicate and categorize simple buckets
        recommendations = {
            "critical": [r for r in recs if "verify" in r.lower() or "check" in r.lower()],
            "performance": [r for r in recs if "usage" in r.lower() or "concurrency" in r.lower()],
            "maintenance": [r for r in recs if r not in set(recs)]
        }

        return {
            "recommendations": recommendations,
            "total_recommendations": sum(len(v) for v in recommendations.values()),
            "health_score": readiness.get("health_score", 0),
            "overall_health": readiness.get("status", "not_ready"),
            "generated_at": readiness.get("timestamp")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/problems")
async def detect_problems(request: Request):
    """
    Run automated problem detection.
    
    Returns detected problems with severity levels and resolution suggestions.
    """
    try:
        # Get clients
        clients = await _get_clients_with_timeout(request, 20)
        
        # Run problem detection
        problems = await problem_detector.detect_problems(
            chroma_client=clients.get('chroma_client'),
            neo4j_client=clients.get('neo4j_client'),
            processor=clients.get('processor'),
            embedding_client=clients.get('embedding_client')
        )
        
        # Generate problem report
        report = await problem_detector.generate_problem_report(problems)
        
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect problems: {str(e)}"
        )


async def _get_clients_with_timeout(request: Request, timeout_seconds: int) -> Dict[str, Any]:
    """Get clients from app state with timeout handling."""
    async def get_clients():
        return {
            'chroma_client': getattr(request.app.state, 'chroma_client', None),
            'neo4j_client': getattr(request.app.state, 'neo4j_client', None),
            'processor': getattr(request.app.state, 'repository_processor', None),
            'embedding_client': getattr(request.app.state, 'embedding_client', None)
        }
    
    return await asyncio.wait_for(get_clients(), timeout=timeout_seconds)