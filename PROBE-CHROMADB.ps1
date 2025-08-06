param()

Write-Host "=== PROBING CHROMADB ENDPOINTS ===" -ForegroundColor Yellow

# Test all possible ChromaDB endpoints to see what's actually available
$endpoints = @(
    "http://localhost:8000/",
    "http://localhost:8000/api",
    "http://localhost:8000/api/v1",
    "http://localhost:8000/api/v1/collections",
    "http://localhost:8000/api/v2", 
    "http://localhost:8000/api/v2/collections",
    "http://localhost:8000/docs",
    "http://localhost:8000/openapi.json"
)

foreach ($endpoint in $endpoints) {
    Write-Host "Testing: $endpoint" -ForegroundColor Cyan
    $response = Invoke-WebRequest -Uri $endpoint -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
    if ($response) {
        Write-Host "  Status: $($response.StatusCode)" -ForegroundColor Green
        if ($response.ContentType -like "*json*" -and $response.Content.Length -lt 500) {
            Write-Host "  Content: $($response.Content)" -ForegroundColor Gray
        } elseif ($response.ContentType -like "*html*") {
            Write-Host "  Content: HTML page available" -ForegroundColor Gray
        } else {
            Write-Host "  Content: $($response.Content.Length) bytes" -ForegroundColor Gray
        }
    } else {
        Write-Host "  Status: FAILED" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "=== CHROMADB PROBE COMPLETED ===" -ForegroundColor Yellow