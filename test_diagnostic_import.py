#!/usr/bin/env python3
"""Test diagnostic service imports."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    print("Testing diagnostic service imports...")
    
    # Test basic imports
    from src.services.diagnostic_service import DiagnosticService
    print("✅ DiagnosticService imported successfully")
    
    from src.services.problem_detector import ProblemDetector
    print("✅ ProblemDetector imported successfully")
    
    # Test router import
    from src.api.routes.diagnostics import router
    print("✅ Diagnostics router imported successfully")
    
    # Test creating instances
    diagnostic_service = DiagnosticService()
    print("✅ DiagnosticService instance created successfully")
    
    problem_detector = ProblemDetector(diagnostic_service)
    print("✅ ProblemDetector instance created successfully")
    
    # Test router endpoints
    print(f"✅ Router has {len(router.routes)} routes")
    for route in router.routes:
        if hasattr(route, 'path'):
            print(f"  - {route.methods} {route.path}")
    
    print("\n🎉 All diagnostic imports successful!")
    
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)