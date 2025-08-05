#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test AI Chat Configuration and Functionality
    
.DESCRIPTION
    Validates AWS Bedrock configuration and tests AI Chat functionality
    without requiring a full system restart.
    
.PARAMETER TestCredentials
    Test AWS credentials and Bedrock access
    
.PARAMETER TestAPI
    Test the chat API endpoint
    
.EXAMPLE
    .\test-ai-chat.ps1                      # Quick configuration check
    .\test-ai-chat.ps1 -TestCredentials     # Test AWS access  
    .\test-ai-chat.ps1 -TestAPI             # Test full API functionality
#>

param(
    [switch]$TestCredentials,
    [switch]$TestAPI
)

$ErrorActionPreference = "Continue"

function Write-TestResult {
    param(
        [string]$Message,
        [string]$Status = "INFO",
        [string]$Color = "White"
    )
    
    $statusIcon = switch ($Status) {
        "PASS" { "✅" }
        "FAIL" { "❌" }  
        "WARN" { "⚠️" }
        "INFO" { "ℹ️" }
        default { "•" }
    }
    
    Write-Host "[$((Get-Date).ToString('HH:mm:ss'))] $statusIcon $Message" -ForegroundColor $Color
}

function Test-EnvConfiguration {
    Write-TestResult "=== Testing .env Configuration ===" "INFO" "Cyan"
    
    # Check if .env exists
    if (-not (Test-Path ".env")) {
        Write-TestResult ".env file not found" "FAIL" "Red"
        return $false
    }
    
    # Read .env file
    $envContent = Get-Content ".env" -Raw
    $configOk = $true
    
    # Check required variables
    $requiredVars = @(
        @{Name="BEDROCK_MODEL_ID"; Pattern="BEDROCK_MODEL_ID=.*anthropic\.claude.*"},
        @{Name="AWS_REGION"; Pattern="AWS_REGION=.*"}
    )
    
    foreach ($var in $requiredVars) {
        if ($envContent -match $var.Pattern) {
            # Extract the value
            $matches = [regex]::Matches($envContent, "$($var.Name)=(.+)")
            if ($matches.Count -gt 0) {
                $value = $matches[0].Groups[1].Value.Trim()
                Write-TestResult "$($var.Name) = $value" "PASS" "Green"
            }
        } else {
            Write-TestResult "$($var.Name) not configured" "FAIL" "Red"
            $configOk = $false
        }
    }
    
    # Check for credentials (either profile or keys)
    $hasProfile = $envContent -match "AWS_PROFILE=([^#\r\n]+)" -and $matches[0].Groups[1].Value.Trim() -ne ""
    $hasKeys = ($envContent -match "AWS_ACCESS_KEY_ID=([^#\r\n]+)" -and $matches[0].Groups[1].Value.Trim() -ne "") -and
               ($envContent -match "AWS_SECRET_ACCESS_KEY=([^#\r\n]+)" -and $matches[0].Groups[1].Value.Trim() -ne "")
    
    if ($hasProfile) {
        $profileName = [regex]::Matches($envContent, "AWS_PROFILE=([^#\r\n]+)")[0].Groups[1].Value.Trim()
        Write-TestResult "AWS Profile configured: $profileName" "PASS" "Green"
    } elseif ($hasKeys) {
        Write-TestResult "AWS Access Keys configured" "PASS" "Green"
    } else {
        Write-TestResult "No AWS credentials configured (uncomment AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)" "FAIL" "Red"
        $configOk = $false
    }
    
    return $configOk
}

function Test-AWSCredentials {
    Write-TestResult "=== Testing AWS Credentials ===" "INFO" "Cyan"
    
    try {
        # Test AWS CLI access
        $awsVersion = aws --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-TestResult "AWS CLI available: $($awsVersion.Split(' ')[0])" "PASS" "Green"
        } else {
            Write-TestResult "AWS CLI not available - install for easier credential management" "WARN" "Yellow"
        }
        
        # Test listing Bedrock models (requires credentials and permissions)
        Write-TestResult "Testing Bedrock access..." "INFO" "White"
        $models = aws bedrock list-foundation-models --region us-east-1 2>$null
        
        if ($LASTEXITCODE -eq 0) {
            Write-TestResult "Bedrock access successful" "PASS" "Green"
            
            # Check if Claude models are available
            $modelsJson = $models | ConvertFrom-Json
            $claudeModels = $modelsJson.modelSummaries | Where-Object { $_.modelId -like "*claude*" }
            
            Write-TestResult "Available Claude models:" "INFO" "White"
            foreach ($model in $claudeModels | Select-Object -First 3) {
                Write-TestResult "  - $($model.modelId)" "INFO" "Gray"
            }
        } else {
            Write-TestResult "Bedrock access failed - check credentials and permissions" "FAIL" "Red"
            Write-TestResult "Required IAM permission: bedrock:ListFoundationModels, bedrock:InvokeModel" "INFO" "Yellow"
            return $false
        }
        
    } catch {
        Write-TestResult "AWS credential test failed: $($_.Exception.Message)" "FAIL" "Red"
        return $false
    }
    
    return $true
}

function Test-ChatAPI {
    Write-TestResult "=== Testing Chat API ===" "INFO" "Cyan"
    
    # Check if API server is running
    try {
        $healthResponse = Invoke-RestMethod -Uri "http://localhost:8081/api/v1/health/" -Method GET -TimeoutSec 10
        Write-TestResult "API server is running" "PASS" "Green"
    } catch {
        Write-TestResult "API server not accessible - start with .\START.ps1 -Mode api" "FAIL" "Red"
        return $false
    }
    
    # Check if chat endpoint exists
    try {
        $chatRequest = @{
            question = "Hello, can you help me understand this codebase?"
            top_k = 3
            min_score = 0.0
            mode = "semantic"
        }
        
        Write-TestResult "Sending test chat request..." "INFO" "White"
        $chatResponse = Invoke-RestMethod -Uri "http://localhost:8081/api/v1/chat/ask" -Method POST -Body ($chatRequest | ConvertTo-Json) -ContentType "application/json" -TimeoutSec 30
        
        if ($chatResponse.answer) {
            Write-TestResult "Chat API working! Response preview:" "PASS" "Green"
            $preview = $chatResponse.answer.Substring(0, [Math]::Min(100, $chatResponse.answer.Length))
            Write-TestResult "  '$preview...'" "INFO" "Gray"
            Write-TestResult "Citations: $($chatResponse.citations.Count)" "INFO" "Gray"
        } else {
            Write-TestResult "Chat API responded but no answer received" "WARN" "Yellow"
        }
        
    } catch {
        Write-TestResult "Chat API test failed: $($_.Exception.Message)" "FAIL" "Red"
        
        # Check if it's a configuration issue
        if ($_.Exception.Message -like "*503*" -or $_.Exception.Message -like "*Chat*") {
            Write-TestResult "This may be a configuration issue - check AWS credentials" "INFO" "Yellow"
        }
        
        return $false
    }
    
    return $true
}

function Test-SystemReadiness {
    Write-TestResult "=== Testing System Readiness ===" "INFO" "Cyan"
    
    # Check required services
    $services = @(
        @{Name="ChromaDB"; Url="http://localhost:8000/api/v2/healthcheck"},
        @{Name="Neo4j"; Url="http://localhost:7474/"},
        @{Name="API Server"; Url="http://localhost:8081/api/v1/health/ready"}
    )
    
    $allHealthy = $true
    
    foreach ($service in $services) {
        try {
            $response = Invoke-WebRequest -Uri $service.Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-TestResult "$($service.Name) is healthy" "PASS" "Green"
            } else {
                Write-TestResult "$($service.Name) returned HTTP $($response.StatusCode)" "WARN" "Yellow"
            }
        } catch {
            Write-TestResult "$($service.Name) is not accessible" "FAIL" "Red"
            $allHealthy = $false
        }
    }
    
    if (-not $allHealthy) {
        Write-TestResult "Start required services with: .\START.ps1" "INFO" "Yellow"
    }
    
    return $allHealthy
}

# Main execution
function Start-AIChat-Test {
    Write-TestResult "AI Chat Configuration Test" "INFO" "Cyan"
    Write-TestResult "============================" "INFO" "White"
    
    $results = @{}
    
    # Always run configuration test
    $results["Configuration"] = Test-EnvConfiguration
    
    # Run additional tests if requested
    if ($TestCredentials) {
        $results["AWS Credentials"] = Test-AWSCredentials
    }
    
    if ($TestAPI) {
        $results["System Readiness"] = Test-SystemReadiness  
        $results["Chat API"] = Test-ChatAPI
    }
    
    # Summary
    Write-TestResult "" "INFO" "White"
    Write-TestResult "============================" "INFO" "White"
    Write-TestResult "TEST SUMMARY" "INFO" "Cyan"
    Write-TestResult "============================" "INFO" "White"
    
    $passed = 0
    $failed = 0
    
    foreach ($test in $results.Keys) {
        if ($results[$test]) {
            Write-TestResult "$test - PASSED" "PASS" "Green"
            $passed++
        } else {
            Write-TestResult "$test - FAILED" "FAIL" "Red"
            $failed++
        }
    }
    
    Write-TestResult "" "INFO" "White"
    Write-TestResult "Results: $passed passed, $failed failed" "INFO" "White"
    
    # Recommendations
    if ($failed -eq 0) {
        Write-TestResult "🎉 AI Chat is ready!" "PASS" "Green"
        Write-TestResult "Visit http://localhost:3000/chat to try it out" "INFO" "Cyan"
    } else {
        Write-TestResult "⚠️ Fix the failed tests before using AI Chat" "WARN" "Yellow"
        if (-not $TestCredentials -and $results["Configuration"] -eq $false) {
            Write-TestResult "Run: .\test-ai-chat.ps1 -TestCredentials" "INFO" "White"
        }
        if (-not $TestAPI) {
            Write-TestResult "Run: .\test-ai-chat.ps1 -TestAPI" "INFO" "White"  
        }
    }
    
    Write-TestResult "" "INFO" "White"
    Write-TestResult "For setup help, see: AI-CHAT-SETUP.md" "INFO" "Cyan"
}

# Execute the test
Start-AIChat-Test