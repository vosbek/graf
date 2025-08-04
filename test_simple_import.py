#!/usr/bin/env python3
"""Simple import test to isolate the issue."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    print("Testing individual imports...")
    
    print("1. Importing exceptions...")
    from core.exceptions import GraphRAGException
    print("   ✓ exceptions imported successfully")
    
    print("2. Importing logging_config...")
    from core.logging_config import get_logger
    print("   ✓ logging_config imported successfully")
    
    print("3. Importing performance_metrics...")
    from core.performance_metrics import performance_collector
    print("   ✓ performance_metrics imported successfully")
    
    print("4. Importing error_handling module...")
    import core.error_handling
    print("   ✓ error_handling module imported successfully")
    
    print("5. Checking error_handling contents...")
    print(f"   Available attributes: {[attr for attr in dir(core.error_handling) if not attr.startswith('_')]}")
    
    print("6. Testing direct function access...")
    if hasattr(core.error_handling, 'get_error_handler'):
        print("   ✓ get_error_handler found")
        handler = core.error_handling.get_error_handler("test")
        print(f"   ✓ Error handler created: {handler}")
    else:
        print("   ✗ get_error_handler not found")
    
    print("7. Testing import from...")
    try:
        from core.error_handling import get_error_handler
        print("   ✓ get_error_handler imported successfully")
    except ImportError as e:
        print(f"   ✗ Import failed: {e}")
        
        # Try to understand why
        print("   Debugging import issue...")
        import importlib
        import core.error_handling
        importlib.reload(core.error_handling)
        print(f"   After reload: {[attr for attr in dir(core.error_handling) if not attr.startswith('_')]}")
    
except Exception as e:
    print(f"Error during import test: {e}")
    import traceback
    traceback.print_exc()