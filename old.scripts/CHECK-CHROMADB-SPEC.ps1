param()

Write-Host "=== CHECKING CHROMADB API SPECIFICATION ===" -ForegroundColor Yellow

# Get the OpenAPI spec to see what endpoints actually exist
$spec = Invoke-WebRequest -Uri "http://localhost:8000/openapi.json" -UseBasicParsing
$json = $spec.Content | ConvertFrom-Json

Write-Host "ChromaDB API Specification:" -ForegroundColor Cyan
Write-Host "Title: $($json.info.title)" -ForegroundColor White
Write-Host "Version: $($json.info.version)" -ForegroundColor White
Write-Host ""

Write-Host "Available Endpoints:" -ForegroundColor Cyan
foreach ($path in $json.paths.PSObject.Properties) {
    $endpoint = $path.Name
    $methods = $path.Value.PSObject.Properties | ForEach-Object { $_.Name.ToUpper() }
    Write-Host "  $endpoint - Methods: $($methods -join ', ')" -ForegroundColor White
}

Write-Host ""
Write-Host "=== CHROMADB SPEC CHECK COMPLETED ===" -ForegroundColor Yellow