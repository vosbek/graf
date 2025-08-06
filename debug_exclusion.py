#!/usr/bin/env python3

import fnmatch
from pathlib import Path

def _matches_exclusion_pattern(file_path: Path, pattern: str, repo_root: Path) -> bool:
    """
    Check if a file path matches an exclusion pattern.
    """
    try:
        # Get relative path from repo root
        relative_path = file_path.relative_to(repo_root)
        
        # Convert to POSIX format for consistent pattern matching
        posix_path = relative_path.as_posix()
        
        print(f"  Testing: {posix_path} against {pattern}")
        
        # Use fnmatch for all patterns - it handles ** patterns correctly
        result = fnmatch.fnmatch(posix_path, pattern)
        print(f"    Result: {result}")
        return result
            
    except (ValueError, OSError) as e:
        print(f"    Error: {e}")
        # If we can't get relative path, return False (don't exclude)
        return False

# Test with a sample Java file
repo_root = Path("C:/devl/workspaces/dependisee")
test_file = Path("C:/devl/workspaces/dependisee/src/main/java/com/company/mapper/DependencyMapper.java")

# Test exclusion patterns
exclude_patterns = [
    "**/target/**", "**/build/**", "**/dist/**", "**/node_modules/**",
    "**/.git/**", "**/*.class", "**/*.jar", "**/*.war", "**/*.ear",
    "**/bin/**", "**/obj/**", "**/*.exe", "**/*.dll", "**/*.so",
    "**/.vscode/**", "**/.idea/**", "**/__pycache__/**", "**/.pytest_cache/**",
    "**/coverage/**", "**/htmlcov/**", "**/.coverage", "**/logs/**",
    "**/tmp/**", "**/temp/**", "**/.DS_Store", "**/Thumbs.db"
]

print(f"Testing file: {test_file}")
print(f"Repo root: {repo_root}")
print(f"Relative path: {test_file.relative_to(repo_root).as_posix()}")
print()

excluded = False
for pattern in exclude_patterns:
    if _matches_exclusion_pattern(test_file, pattern, repo_root):
        excluded = True
        print(f"EXCLUDED by pattern: {pattern}")
        break

if not excluded:
    print("File NOT excluded - should be processed!")
else:
    print("File IS excluded - will be skipped!")