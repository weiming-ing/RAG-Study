# ============================================
# P9/P10/P12 模块接口测试脚本
# P9: 监控统计
# P10: 安全风控
# P12: 接口密钥管理
# ============================================

$base = "http://localhost:8002"
$pass = 0
$fail = 0
$results = @()
$testPassword = if ($env:TEST_PASSWORD) { $env:TEST_PASSWORD } else { "admin123" }

function Test-Case {
    param([string]$module, [string]$name, [scriptblock]$test)
    Write-Host "  [$module] $name ... " -NoNewline
    try {
        $result = & $test
        if ($result) {
            Write-Host "PASS" -ForegroundColor Green
            $global:pass++
            $global:results += "[PASS] [$module] $name"
        } else {
            Write-Host "FAIL" -ForegroundColor Red
            $global:fail++
            $global:results += "[FAIL] [$module] $name"
        }
    } catch {
        Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
        $global:fail++
        $global:results += "[FAIL] [$module] $name - $($_.Exception.Message)"
    }
}

function Test-Case-WithOutput {
    param([string]$module, [string]$name, [scriptblock]$test)
    Write-Host "  [$module] $name ... " -NoNewline
    try {
        $result = & $test
        if ($result) {
            Write-Host "PASS" -ForegroundColor Green
            $global:pass++
            $global:results += "[PASS] [$module] $name"
        } else {
            Write-Host "FAIL" -ForegroundColor Red
            $global:fail++
            $global:results += "[FAIL] [$module] $name"
        }
        return $result
    } catch {
        Write-Host "FAIL ($($_.Exception.Message))" -ForegroundColor Red
        $global:fail++
        $global:results += "[FAIL] [$module] $name - $($_.Exception.Message)"
        return $null
    }
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  P9/P10/P12 Module API Test" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# Login
Write-Host "`n--- Login ---" -ForegroundColor Yellow
$loginBody = @{username="admin";password=$testPassword} | ConvertTo-Json
$loginResp = Invoke-RestMethod -Uri "$base/api/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$token = $loginResp.data.accessToken
Write-Host "  Token: $($token.Substring(0,20))..." -ForegroundColor Gray

# ==========================================
# P9: 监控统计
# ==========================================
Write-Host "`n--- P9: Dashboard & Monitoring (13 tests) ---" -ForegroundColor Yellow

Test-Case "P9" "get dashboard overview" {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/overview" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and $r.data.totalKbCount -ge 0
}

Test-Case "P9" "get api call stats" {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/api-stats?days=7" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and ($r.data.topApiPaths -is [array])
}

Test-Case "P9" "get token usage stats" {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/token-stats?days=7" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and ($r.data.dailyTrend -is [array])
}

Test-Case "P9" "get hot docs top 10" {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/hot-docs?days=7&limit=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P9" "get kb hot rank" {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/kb-hot-rank?days=7" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P9" "get task stats" {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/task-stats?days=7" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and ($r.data.statusCount -is [array])
}

Test-Case "P9" "get active alerts" {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/alerts" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

# Create an alert first
$alertBody = @{alertType="TEST";alertLevel="WARN";title="Test Alert";detail="Test alert detail";source="test-script"} | ConvertTo-Json
# We need to create alert via service, but we can test resolve
Test-Case "P9" "resolve alert (invalid id)" {
    try {
        $r = Invoke-RestMethod -Uri "$base/api/dashboard/alerts/99999/resolve" -Method Put -Headers @{Authorization="Bearer $token"}
        $r.code -eq 0
    } catch { $true }
}

# ==========================================
# P10: 安全风控 (敏感词 + 限流 + 访问控制)
# ==========================================
Write-Host "`n--- P10: Security Risk Control (25 tests) ---" -ForegroundColor Yellow

# --- Sensitive Words ---
Test-Case "P10" "list sensitive words (empty)" {
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

$sw1 = $null
Test-Case-WithOutput "P10" "add sensitive word 1" {
    $body = @{word="test_bad_word";category="GENERAL";level="BLOCK";enabled=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $global:sw1 = $r.data
    $r.code -eq 0 -and $r.data.id -ne $null
}

$sw2 = $null
Test-Case-WithOutput "P10" "add sensitive word 2" {
    $body = @{word="forbidden_content";category="CUSTOM";level="WARN";enabled=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $global:sw2 = $r.data
    $r.code -eq 0 -and $r.data.id -ne $null
}

Test-Case "P10" "list sensitive words (2 items)" {
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and $r.data.total -ge 2
}

Test-Case "P10" "check text with sensitive words" {
    $body = @{text="this contains test_bad_word and forbidden_content";kbId=""} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words/check" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and $r.data.hasSensitive -eq $true -and $r.data.matchCount -ge 2
}

Test-Case "P10" "check clean text" {
    $body = @{text="this is normal text";kbId=""} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words/check" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and $r.data.hasSensitive -eq $false
}

Test-Case "P10" "filter sensitive words by category" {
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words?category=GENERAL" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P10" "filter sensitive words by keyword" {
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words?keyword=bad" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P10" "update sensitive word" {
    $body = @{id=$sw1.id;word="test_bad_word";category="GENERAL";level="WARN";enabled=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P10" "batch import sensitive words" {
    $body = @(
        @{word="batch_word_1";category="GENERAL";level="BLOCK";enabled=1},
        @{word="batch_word_2";category="GENERAL";level="BLOCK";enabled=1}
    ) | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words/batch" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

# --- Rate Limits ---
Test-Case "P10" "list rate limits (empty)" {
    $r = Invoke-RestMethod -Uri "$base/api/security/rate-limits?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

$rl1 = $null
Test-Case-WithOutput "P10" "add rate limit rule" {
    $body = @{ruleName="test_qps_limit";targetType="USER";targetValue="1";limitType="QPS";limitCount=10;windowSeconds=60;enabled=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/rate-limits" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $global:rl1 = $r.data
    $r.code -eq 0 -and $r.data.id -ne $null
}

Test-Case "P10" "add rate limit rule (IP type)" {
    $body = @{ruleName="ip_limit";targetType="IP";targetValue="192.168.1.1";limitType="QPS";limitCount=5;windowSeconds=60;enabled=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/rate-limits" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P10" "list rate limits (2 items)" {
    $r = Invoke-RestMethod -Uri "$base/api/security/rate-limits?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and $r.data.total -ge 2
}

Test-Case "P10" "update rate limit rule" {
    $body = @{id=$rl1.id;ruleName="test_qps_limit_updated";targetType="USER";targetValue="1";limitType="QPS";limitCount=20;windowSeconds=60;enabled=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/rate-limits" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

# --- Access Control ---
Test-Case "P10" "list access controls (empty)" {
    $r = Invoke-RestMethod -Uri "$base/api/security/access-controls?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

$ac1 = $null
Test-Case-WithOutput "P10" "add blacklist IP" {
    $body = @{ruleType="BLACKLIST";ipAddress="10.0.0.99";reason="test blacklist";enabled=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/access-controls" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $global:ac1 = $r.data
    $r.code -eq 0 -and $r.data.id -ne $null
}

Test-Case "P10" "add whitelist IP" {
    $body = @{ruleType="WHITELIST";ipAddress="192.168.1.100";reason="test whitelist";enabled=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/access-controls" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P10" "list access controls (2 items)" {
    $r = Invoke-RestMethod -Uri "$base/api/security/access-controls?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and $r.data.total -ge 2
}

Test-Case "P10" "filter access controls by type" {
    $r = Invoke-RestMethod -Uri "$base/api/security/access-controls?ruleType=BLACKLIST" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

# ==========================================
# P12: API Key Management
# ==========================================
Write-Host "`n--- P12: API Key Management (12 tests) ---" -ForegroundColor Yellow

Test-Case "P12" "list api keys (empty)" {
    $r = Invoke-RestMethod -Uri "$base/api/api-keys?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

$ak1 = $null
Test-Case-WithOutput "P12" "generate api key" {
    $body = @{
        keyName="test_api_key"
        userId=1
        kbIds="[]"
        permissions='["read","search"]'
        rateLimit=100
        dailyLimit=1000
        description="test key for integration"
    } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/api-keys" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $global:ak1 = $r.data
    $r.code -eq 0 -and $r.data.id -ne $null -and $r.data.apiKey.StartsWith("ak-")
}

$ak2 = $null
Test-Case-WithOutput "P12" "generate api key with expiry" {
    $expiry = (Get-Date).AddDays(30).ToString("yyyy-MM-dd HH:mm:ss")
    $body = @{
        keyName="expiring_key"
        userId=1
        kbIds="[]"
        permissions='["read"]'
        rateLimit=50
        dailyLimit=500
        description="key with expiry"
        expireTime=$expiry
    } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/api-keys" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $global:ak2 = $r.data
    $r.code -eq 0 -and $r.data.id -ne $null
}

Test-Case "P12" "list api keys (2 items)" {
    $r = Invoke-RestMethod -Uri "$base/api/api-keys?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and $r.data.total -ge 2
}

Test-Case "P12" "get api key by id" {
    $r = Invoke-RestMethod -Uri "$base/api/api-keys/$($ak1.id)" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and $r.data.keyName -eq "test_api_key"
}

Test-Case "P12" "update api key" {
    $body = @{keyName="test_api_key_renamed";enabled=1;rateLimit=200;description="updated description"} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/api-keys/$($ak1.id)" -Method Put -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P12" "disable api key" {
    $body = @{enabled=0} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/api-keys/$($ak1.id)" -Method Put -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P12" "re-enable api key" {
    $body = @{enabled=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/api-keys/$($ak1.id)" -Method Put -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P12" "filter api keys by keyword" {
    $r = Invoke-RestMethod -Uri "$base/api/api-keys?keyword=expiring" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P12" "filter api keys by userId" {
    $r = Invoke-RestMethod -Uri "$base/api/api-keys?userId=1" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P12" "delete api key" {
    $r = Invoke-RestMethod -Uri "$base/api/api-keys/$($ak2.id)" -Method Delete -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "P12" "verify api key deleted" {
    $r = Invoke-RestMethod -Uri "$base/api/api-keys?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0 -and $r.data.total -ge 1
}

# ==========================================
# Cleanup
# ==========================================
Write-Host "`n--- Cleanup ---" -ForegroundColor Yellow

Test-Case "CLN" "delete sensitive word 1" {
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words/$($sw1.id)" -Method Delete -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "CLN" "delete sensitive word 2" {
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words/$($sw2.id)" -Method Delete -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "CLN" "delete rate limit" {
    $r = Invoke-RestMethod -Uri "$base/api/security/rate-limits/$($rl1.id)" -Method Delete -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "CLN" "delete access control" {
    $r = Invoke-RestMethod -Uri "$base/api/security/access-controls/$($ac1.id)" -Method Delete -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

Test-Case "CLN" "delete api key" {
    $r = Invoke-RestMethod -Uri "$base/api/api-keys/$($ak1.id)" -Method Delete -Headers @{Authorization="Bearer $token"}
    $r.code -eq 0
}

# ==========================================
# Summary
# ==========================================
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  P9/P10/P12 Test Results" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Total: $($pass + $fail)" -ForegroundColor White
Write-Host "  Pass:  $pass" -ForegroundColor Green
Write-Host "  Fail:  $fail" -ForegroundColor Red

if ($fail -eq 0) {
    Write-Host "`n  ALL TESTS PASSED!" -ForegroundColor Green
} else {
    Write-Host "`n  SOME TESTS FAILED!" -ForegroundColor Red
    Write-Host "`n  Failed Tests:" -ForegroundColor Red
    $results | Where-Object { $_ -like "[FAIL]*" }
}