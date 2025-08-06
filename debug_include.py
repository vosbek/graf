#!/usr/bin/env python3

from pathlib import Path

# Test include patterns
repo_path = Path("C:/devl/workspaces/dependisee")
include_patterns = [
    "**/*.java", "**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx",
    "**/*.go", "**/*.rs", "**/*.cpp", "**/*.c", "**/*.h", "**/*.hpp",
    "**/*.cs", "**/*.php", "**/*.rb", "**/*.scala", "**/*.kt", "**/*.swift"
]

print(f"Repository path: {repo_path}")
print(f"Path exists: {repo_path.exists()}")
print()

total_files = 0
for pattern in include_patterns:
    print(f"Testing pattern: {pattern}")
    try:
        pattern_files = list(repo_path.glob(pattern))
        print(f"  Found {len(pattern_files)} files")
        total_files += len(pattern_files)
        
        # Show first few files
        for i, file_path in enumerate(pattern_files[:3]):
            relative_path = file_path.relative_to(repo_path)
            print(f"    {i+1}. {relative_path}")
        
        if len(pattern_files) > 3:
            print(f"    ... and {len(pattern_files) - 3} more")
            
    except Exception as e:
        print(f"  Error: {e}")
    print()

print(f"Total files found by include patterns: {total_files}")