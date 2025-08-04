#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Bootstrap and start the API in foreground with clear logging.

.DESCRIPTION
  - Validates Python availability and version
  - (Optional) Creates and activates a venv
  - Installs backend dependencies from requirements.txt
  - Exports required environment variables
  - Starts uvicorn in foreground so errors are visible

.PARAMETER UseVenv
  Create and use a Python venv at .venv (default: false)

.PARAMETER SkipInstall
  Skip 'pip install -r requirements.txt' (default: false)

.PARAMETER Port
  API port (default: 8080)
#>

param(
  [switch]$UseVenv = $false,
  [switch]$SkipInstall = $false,
  [int]$Port = 8080
)

$ErrorActionPreference = "Stop"

function Section { param([string]$Title) Write-Host "`n=== $Title ===" -ForegroundColor Cyan }

Section "Python"
try {
  $pyv = python --version
  Write-Host "Python: $pyv" -ForegroundColor Green
} catch {
  Write-Error "Python not found. Install Python 3.11+ and ensure 'python' is on PATH."
  exit 1
}

if ($UseVenv) {
  Section "Virtualenv"
  if (-not (Test-Path ".\.venv")) {
    Write-Host "Creating venv at .\.venv" -ForegroundColor Yellow
    python -m venv .venv
  }
  Write-Host "Activating venv" -ForegroundColor Yellow
  . .\.venv\Scripts\Activate.ps1
}

if (-not $SkipInstall) {
  Section "Installing dependencies"
  if (-not (Test-Path ".\requirements.txt")) {
    Write-Error "requirements.txt not found at repo root."
    exit 1
  }
  python -m pip install --upgrade pip
  pip install -r requirements.txt
}

Section "Exporting environment"
$env:APP_ENV = "development"
$env:API_HOST = "0.0.0.0"
$env:API_PORT = "$Port"
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USERNAME = "neo4j"
$env:NEO4J_PASSWORD = "codebase-rag-2024"
$env:NEO4J_DATABASE = "neo4j"
$env:CHROMA_HOST = "localhost"
$env:CHROMA_PORT = "8000"
$env:LOG_LEVEL = "INFO"
$env:EMBEDDING_MODEL = "microsoft/codebert-base"
$env:AUTH_ENABLED = "false"

Write-Host "API_PORT: $Port" -ForegroundColor Gray
Write-Host "NEO4J_URI: $($env:NEO4J_URI)" -ForegroundColor Gray
Write-Host "CHROMA: $($env:CHROMA_HOST):$($env:CHROMA_PORT)" -ForegroundColor Gray

Section "Starting API (foreground)"
Write-Host "If the server exits, scroll up to the first ERROR or traceback for the root cause." -ForegroundColor Yellow
python -m uvicorn src.main:app --host 0.0.0.0 --port $Port --log-level info