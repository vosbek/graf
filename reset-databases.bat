@echo off
REM Database Reset Batch Script for Windows
REM Clears Neo4j and ChromaDB for clean re-indexing

echo =========================================
echo Enhanced Codebase Ingestion - Database Reset
echo =========================================
echo.

REM Check if we're in the right directory
if not exist "scripts\cleanup-databases.py" (
    echo ERROR: Please run this script from the project root directory
    echo Expected to find: scripts\cleanup-databases.py
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not available or not in PATH
    echo Please install Python or add it to your PATH
    pause
    exit /b 1
)

echo Choose reset option:
echo 1. Reset both databases (Neo4j + ChromaDB)
echo 2. Reset Neo4j only (business relationships)
echo 3. Reset ChromaDB only (embeddings)
echo 4. Dry run (preview what would be deleted)
echo 5. Reset with backup
echo 6. Cancel
echo.
set /p choice="Enter your choice (1-6): "

if "%choice%"=="1" (
    echo.
    echo Resetting both Neo4j and ChromaDB databases...
    python scripts\cleanup-databases.py
) else if "%choice%"=="2" (
    echo.
    echo Resetting Neo4j database only...
    python scripts\cleanup-databases.py --neo4j-only
) else if "%choice%"=="3" (
    echo.
    echo Resetting ChromaDB database only...
    python scripts\cleanup-databases.py --chroma-only
) else if "%choice%"=="4" (
    echo.
    echo Running dry run (preview mode)...
    python scripts\cleanup-databases.py --dry-run
) else if "%choice%"=="5" (
    echo.
    echo Resetting with backup...
    python scripts\cleanup-databases.py --backup
) else if "%choice%"=="6" (
    echo Operation cancelled.
    pause
    exit /b 0
) else (
    echo Invalid choice. Please run the script again.
    pause
    exit /b 1
)

echo.
if errorlevel 1 (
    echo Database reset encountered an error.
    echo Check the output above for details.
) else (
    echo Database reset completed successfully!
    echo.
    echo Next steps:
    echo 1. Verify system health in the web UI (System Status page)
    echo 2. Re-index your repositories to test enhanced ingestion
    echo 3. Check dependency graph for business relationships
)

echo.
pause