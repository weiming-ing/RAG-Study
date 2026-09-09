# ============================================
# P3 System Configuration API Test
# ============================================
$base = "http://localhost:8002"
$pass = 0; $fail = 0
$testPassword = if ($env:TEST_PASSWORD) { $env:TEST_PASSWORD } else { "admin123" }

function Test-Pass($n, $d) { $script:pass++; Write-Host "  PASS: $n $d" -ForegroundColor Green }
function Test-Fail($n, $d) { $script:fail++; Write-Host "  FAIL: $n $d" -ForegroundColor Red }

# Login
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Login" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
$loginBody = "{`"username`":`"admin`",`"password`":`"$testPassword`"}"
$loginResp = Invoke-RestMethod -Uri "$base/api/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$token = $loginResp.data.accessToken
Write-Host "  Token: $($token.Substring(0,20))..."

# ==========================================
# P3: System Configuration Management
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P3: System Configuration (9 tests)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [P3-1] List all configs
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/configs?page=1&size=50" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) {
        Test-Pass "P3-1" "list configs count=$($r.data.records.Count)"
    } else {
        Test-Fail "P3-1" "list configs failed"
    }
} catch { Test-Fail "P3-1" "$($_.Exception.Message)" }

# [P3-2] List configs by group
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/configs?group=LLM" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array] -and $r.data.records.Count -ge 1) {
        Test-Pass "P3-2" "filter by group LLM count=$($r.data.records.Count)"
    } else {
        Test-Fail "P3-2" "filter by group failed"
    }
} catch { Test-Fail "P3-2" "$($_.Exception.Message)" }

# [P3-3] Search configs by keyword
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/configs?keyword=model" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array] -and $r.data.records.Count -ge 1) {
        Test-Pass "P3-3" "search keyword=model count=$($r.data.records.Count)"
    } else {
        Test-Fail "P3-3" "search keyword failed"
    }
} catch { Test-Fail "P3-3" "$($_.Exception.Message)" }

# [P3-4] Get config by group
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/configs/group/RAG" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data -ne $null) {
        Test-Pass "P3-4" "get RAG group configs"
    } else {
        Test-Fail "P3-4" "get group configs failed"
    }
} catch { Test-Fail "P3-4" "$($_.Exception.Message)" }

# [P3-5] Get all configs grouped
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/configs/grouped" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data -ne $null) {
        Test-Pass "P3-5" "get all grouped configs"
    } else {
        Test-Fail "P3-5" "get grouped configs failed"
    }
} catch { Test-Fail "P3-5" "$($_.Exception.Message)" }

# [P3-6] Update config
Write-Host ""
try {
    $body = @{configKey="test.new.config"; configValue="test-value"; configType="STRING"; configGroup="GENERAL"; description="Test config"} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/system/configs" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) {
        Test-Pass "P3-6" "save new config"
    } else {
        Test-Fail "P3-6" "save config failed"
    }
} catch { Test-Fail "P3-6" "$($_.Exception.Message)" }

# [P3-7] Batch update configs
Write-Host ""
try {
    $body = @(
        @{configKey="system.name"; configValue="RAG管理系统"},
        @{configKey="system.version"; configValue="1.1.0"}
    ) | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/system/configs/batch" -Method Put -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.updatedCount -eq 2) {
        Test-Pass "P3-7" "batch update 2 configs"
    } else {
        Test-Fail "P3-7" "batch update failed"
    }
} catch { Test-Fail "P3-7" "$($_.Exception.Message)" }

# [P3-8] Get config stats
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/configs/stats" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data -is [array]) {
        Test-Pass "P3-8" "config stats count=$($r.data.Count)"
    } else {
        Test-Fail "P3-8" "config stats failed"
    }
} catch { Test-Fail "P3-8" "$($_.Exception.Message)" }

# [P3-9] Get log stats
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/logs/stats?days=7" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data -ne $null) {
        Test-Pass "P3-9" "log stats"
    } else {
        Test-Fail "P3-9" "log stats failed"
    }
} catch { Test-Fail "P3-9" "$($_.Exception.Message)" }

# ==========================================
# P3: System Log Management
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P3: System Logs (4 tests)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [P3-10] List logs
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/logs?page=1&size=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) {
        Test-Pass "P3-10" "list logs count=$($r.data.records.Count)"
    } else {
        Test-Fail "P3-10" "list logs failed"
    }
} catch { Test-Fail "P3-10" "$($_.Exception.Message)" }

# [P3-11] Filter logs by level
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/logs?level=ERROR" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) {
        Test-Pass "P3-11" "filter ERROR logs count=$($r.data.records.Count)"
    } else {
        Test-Fail "P3-11" "filter logs failed"
    }
} catch { Test-Fail "P3-11" "$($_.Exception.Message)" }

# [P3-12] Filter logs by module
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/logs?module=Auth" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) {
        Test-Pass "P3-12" "filter Auth module logs"
    } else {
        Test-Fail "P3-12" "filter module logs failed"
    }
} catch { Test-Fail "P3-12" "$($_.Exception.Message)" }

# [P3-13] Clean expired logs
Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/logs/clean?days=365" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.cleanedCount -ge 0) {
        Test-Pass "P3-13" "clean expired logs count=$($r.data.cleanedCount)"
    } else {
        Test-Fail "P3-13" "clean logs failed"
    }
} catch { Test-Fail "P3-13" "$($_.Exception.Message)" }

# ==========================================
# Results
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P3 Test Results" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
$total = $pass + $fail
Write-Host "  Total: $total" -ForegroundColor White
Write-Host "  Pass:  $pass" -ForegroundColor Green
Write-Host "  Fail:  $fail" -ForegroundColor Red
if ($fail -eq 0) {
    Write-Host "`n  ALL TESTS PASSED!" -ForegroundColor Green
} else {
    Write-Host "`n  $fail test(s) FAILED!" -ForegroundColor Red
}