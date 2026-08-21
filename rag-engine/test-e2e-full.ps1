# ============================================
# Full E2E Functional Test - 全模块功能测试
# 覆盖: P1-P12+P3 所有模块 (基于真实API路径)
# ============================================
$base = "http://localhost:8002"
$pass = 0; $fail = 0

function Test-Pass($n, $d) { $script:pass++; Write-Host "  [PASS] $n | $d" -ForegroundColor Green }
function Test-Fail($n, $d) { $script:fail++; Write-Host "  [FAIL] $n | $d" -ForegroundColor Red }
function Header($t) { Write-Host "`n========================================" -ForegroundColor Cyan; Write-Host "  $t" -ForegroundColor Cyan; Write-Host "========================================" -ForegroundColor Cyan }

# ==========================================
# 1. P1: 认证模块
# ==========================================
Header "P1: Authentication"

Write-Host ""
try {
    $body = '{"username":"admin","password":"admin123"}'
    $r = Invoke-RestMethod -Uri "$base/api/auth/login" -Method Post -Body $body -ContentType "application/json"
    $token = $r.data.accessToken
    if ($r.code -eq 0 -and $token) { Test-Pass "P1-1" "login success" } else { Test-Fail "P1-1" "login failed" }
} catch { Test-Fail "P1-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/auth/me" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.username -eq "admin") { Test-Pass "P1-2" "get user info (/auth/me)" } else { Test-Fail "P1-2" "user info failed" }
} catch { Test-Fail "P1-2" "$($_.Exception.Message)" }

Write-Host ""
try {
    $uname = "testuser_e2e_" + (Get-Random -Minimum 1000 -Maximum 9999)
    $body = "{`"username`":`"$uname`",`"password`":`"Pass123!`",`"displayName`":`"E2E Test User`"}"
    $r = Invoke-RestMethod -Uri "$base/api/auth/register" -Method Post -Body $body -ContentType "application/json"
    if ($r.code -eq 0) { Test-Pass "P1-3" "register user $uname" } else { Test-Fail "P1-3" "register failed" }
} catch { Test-Fail "P1-3" "$($_.Exception.Message)" }

# ==========================================
# 2. P2: 用户/角色/菜单管理
# ==========================================
Header "P2: User/Role/Menu Management"

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/admin/users?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) { Test-Pass "P2-1" "list users count=$($r.data.records.Count)" } else { Test-Fail "P2-1" "list users failed" }
} catch { Test-Fail "P2-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/admin/roles?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) { Test-Pass "P2-2" "list roles count=$($r.data.records.Count)" } else { Test-Fail "P2-2" "list roles failed" }
} catch { Test-Fail "P2-2" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/admin/menus/tree" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P2-3" "get menu tree" } else { Test-Fail "P2-3" "menu tree failed" }
} catch { Test-Fail "P2-3" "$($_.Exception.Message)" }

Write-Host ""
try {
    $uname2 = "e2e_user_" + (Get-Random -Minimum 1000 -Maximum 9999)
    $body = "{`"username`":`"$uname2`",`"password`":`"Test123!`",`"displayName`":`"E2E Test`",`"email`":`"e2e@test.com`"}"
    $r = Invoke-RestMethod -Uri "$base/api/admin/users" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { $newUserId = $r.data.id; Test-Pass "P2-4" "create user id=$newUserId" } else { Test-Fail "P2-4" "create user failed" }
} catch { Test-Fail "P2-4" "$($_.Exception.Message)" }

Write-Host ""
try {
    $body = '{"roleName":"E2E Test Role","roleCode":"ROLE_E2E_TEST","description":"E2E test role"}'
    $r = Invoke-RestMethod -Uri "$base/api/admin/roles" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { $newRoleId = $r.data.id; Test-Pass "P2-5" "create role id=$newRoleId" } else { Test-Fail "P2-5" "create role failed" }
} catch { Test-Fail "P2-5" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($newRoleId) {
        $r = Invoke-RestMethod -Uri "$base/api/admin/roles/$newRoleId" -Method Delete -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "P2-6" "delete role" } else { Test-Fail "P2-6" "delete role failed" }
    }
} catch { Test-Fail "P2-6" "$($_.Exception.Message)" }

# ==========================================
# 3. P3: 系统配置管理
# ==========================================
Header "P3: System Configuration"

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/configs?page=1&size=20" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) { Test-Pass "P3-1" "list configs count=$($r.data.records.Count)" } else { Test-Fail "P3-1" "list configs failed" }
} catch { Test-Fail "P3-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/configs/grouped" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data -ne $null) { Test-Pass "P3-2" "get grouped configs" } else { Test-Fail "P3-2" "grouped configs failed" }
} catch { Test-Fail "P3-2" "$($_.Exception.Message)" }

Write-Host ""
try {
    $body = @{configKey="e2e.test.config"; configValue="e2e-test-value"; configType="STRING"; configGroup="GENERAL"; description="E2E Test Config"} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/system/configs" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { $configId = $r.data.id; Test-Pass "P3-3" "create config" } else { Test-Fail "P3-3" "create config failed" }
} catch { Test-Fail "P3-3" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/system/logs?page=1&size=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P3-4" "list logs" } else { Test-Fail "P3-4" "list logs failed" }
} catch { Test-Fail "P3-4" "$($_.Exception.Message)" }

# ==========================================
# 4. P4: 知识库管理
# ==========================================
Header "P4: Knowledge Base"

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/knowledge-bases?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) { Test-Pass "P4-1" "list KB count=$($r.data.records.Count)" } else { Test-Fail "P4-1" "list KB failed" }
} catch { Test-Fail "P4-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    $geekId = [System.Guid]::NewGuid().ToString().Substring(0, 8)
    $body = @{name="E2E-Test-KB-$geekId"; description="E2E test knowledge base"; category="TEST"; isPublic=1} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/knowledge-bases" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.id) { $kbId = $r.data.id; Test-Pass "P4-2" "create KB id=$kbId" } else { Test-Fail "P4-2" "create KB failed" }
} catch { Test-Fail "P4-2" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($kbId) {
        $r = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId" -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "P4-3" "get KB detail" } else { Test-Fail "P4-3" "get KB detail failed" }
    }
} catch { Test-Fail "P4-3" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($kbId) {
        $body = @{name="E2E-Updated-KB"; description="Updated description"} | ConvertTo-Json
        $r = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId" -Method Put -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "P4-4" "update KB" } else { Test-Fail "P4-4" "update KB failed" }
    }
} catch { Test-Fail "P4-4" "$($_.Exception.Message)" }

# ==========================================
# 5. P5: 文档管理
# ==========================================
Header "P5: Document Management"

Write-Host ""
try {
    if ($kbId) {
        $r = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents?pageNum=1&pageSize=20" -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0 -and $r.data.records -is [array]) { Test-Pass "P5-1" "list documents (KB=$kbId) count=$($r.data.records.Count)" } else { Test-Fail "P5-1" "list documents failed" }
    }
} catch { Test-Fail "P5-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($kbId) {
        $docBody = @{name="e2e-test-doc.txt"; content="This is an E2E test document content. It contains information about RAG systems and knowledge management."; fileType="txt"} | ConvertTo-Json
        $r = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/manual" -Method Post -Body $docBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0 -and $r.data.id) { $docId = $r.data.id; Test-Pass "P5-2" "create document id=$docId" } else { Test-Fail "P5-2" "create document failed" }
    }
} catch { Test-Fail "P5-2" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($docId) {
        $r = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId" -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "P5-3" "get document detail" } else { Test-Fail "P5-3" "get doc detail failed" }
    }
} catch { Test-Fail "P5-3" "$($_.Exception.Message)" }

# ==========================================
# 6. P6: 分块/向量管理
# ==========================================
Header "P6: Chunk/Vector Management"

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/chunks?pageNum=1&pageSize=20" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) { Test-Pass "P6-1" "list chunks count=$($r.data.records.Count)" } else { Test-Fail "P6-1" "list chunks failed" }
} catch { Test-Fail "P6-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($docId) {
        $r = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId/chunks" -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "P6-2" "get document chunks" } else { Test-Fail "P6-2" "get doc chunks failed" }
    }
} catch { Test-Fail "P6-2" "$($_.Exception.Message)" }

# ==========================================
# 7. P7: 检索调试
# ==========================================
Header "P7: Search/Debug"

Write-Host ""
try {
    $body = @{query="test RAG knowledge management"; topK=5; enableHybrid=$true; similarityThreshold=0.0; vectorWeight=0.7; keywordWeight=0.3} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/debug/search" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P7-1" "debug search" } else { Test-Fail "P7-1" "debug search failed" }
} catch { Test-Fail "P7-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/debug/test-cases?pageNum=1&pageSize=5" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P7-2" "list test cases" } else { Test-Fail "P7-2" "list test cases failed" }
} catch { Test-Fail "P7-2" "$($_.Exception.Message)" }

# ==========================================
# 8. P8: 对话/审计日志
# ==========================================
Header "P8: Conversation/Audit"

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/conversations?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) { Test-Pass "P8-1" "list conversations count=$($r.data.records.Count)" } else { Test-Fail "P8-1" "list conversations failed" }
} catch { Test-Fail "P8-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/audit-logs?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) { Test-Pass "P8-2" "list audit logs count=$($r.data.records.Count)" } else { Test-Fail "P8-2" "list audit logs failed" }
} catch { Test-Fail "P8-2" "$($_.Exception.Message)" }

# ==========================================
# 9. P9: 监控统计
# ==========================================
Header "P9: Dashboard/Monitoring"

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/overview" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P9-1" "dashboard overview" } else { Test-Fail "P9-1" "dashboard overview failed" }
} catch { Test-Fail "P9-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/api-stats?days=7" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P9-2" "API call stats" } else { Test-Fail "P9-2" "API call stats failed" }
} catch { Test-Fail "P9-2" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/token-stats?days=7" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P9-3" "token usage stats" } else { Test-Fail "P9-3" "token usage stats failed" }
} catch { Test-Fail "P9-3" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/hot-docs?days=7" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P9-4" "doc hot stats" } else { Test-Fail "P9-4" "doc hot stats failed" }
} catch { Test-Fail "P9-4" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/task-stats?days=7" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P9-5" "task stats" } else { Test-Fail "P9-5" "task stats failed" }
} catch { Test-Fail "P9-5" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/dashboard/alerts" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P9-6" "system alerts" } else { Test-Fail "P9-6" "system alerts failed" }
} catch { Test-Fail "P9-6" "$($_.Exception.Message)" }

# ==========================================
# 10. P10: 安全风控
# ==========================================
Header "P10: Security"

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P10-1" "list sensitive words" } else { Test-Fail "P10-1" "list sensitive words failed" }
} catch { Test-Fail "P10-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    $body = @{word="e2e-test-badword"; category="TEST"; severity="LOW"} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { $swId = $r.data.id; Test-Pass "P10-2" "create sensitive word" } else { Test-Fail "P10-2" "create sensitive word failed" }
} catch { Test-Fail "P10-2" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/security/rate-limits?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P10-3" "list rate limits" } else { Test-Fail "P10-3" "list rate limits failed" }
} catch { Test-Fail "P10-3" "$($_.Exception.Message)" }

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/security/access-controls?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0) { Test-Pass "P10-4" "list access controls" } else { Test-Fail "P10-4" "list access controls failed" }
} catch { Test-Fail "P10-4" "$($_.Exception.Message)" }

# ==========================================
# 11. P12: API密钥管理
# ==========================================
Header "P12: API Key Management"

Write-Host ""
try {
    $r = Invoke-RestMethod -Uri "$base/api/api-keys?pageNum=1&pageSize=10" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.records -is [array]) { Test-Pass "P12-1" "list API keys count=$($r.data.records.Count)" } else { Test-Fail "P12-1" "list API keys failed" }
} catch { Test-Fail "P12-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    $body = @{keyName="E2E Test Key"; description="E2E test API key"; permissions="READ"; rateLimit=100} | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$base/api/api-keys" -Method Post -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($r.code -eq 0 -and $r.data.id) { $apiKeyId = $r.data.id; Test-Pass "P12-2" "create API key id=$apiKeyId" } else { Test-Fail "P12-2" "create API key failed" }
} catch { Test-Fail "P12-2" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($apiKeyId) {
        $body = @{keyName="E2E Updated Key"; enabled=0} | ConvertTo-Json
        $r = Invoke-RestMethod -Uri "$base/api/api-keys/$apiKeyId" -Method Put -Body $body -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "P12-3" "update API key" } else { Test-Fail "P12-3" "update API key failed" }
    }
} catch { Test-Fail "P12-3" "$($_.Exception.Message)" }

# ==========================================
# Cleanup
# ==========================================
Header "Cleanup"

Write-Host ""
try {
    if ($apiKeyId) {
        $r = Invoke-RestMethod -Uri "$base/api/api-keys/$apiKeyId" -Method Delete -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "CLN-1" "delete API key" } else { Test-Fail "CLN-1" "delete API key failed" }
    }
} catch { Test-Fail "CLN-1" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($swId) {
        $r = Invoke-RestMethod -Uri "$base/api/security/sensitive-words/$swId" -Method Delete -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "CLN-2" "delete sensitive word" } else { Test-Fail "CLN-2" "delete sensitive word failed" }
    }
} catch { Test-Fail "CLN-2" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($docId) {
        $r = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId" -Method Delete -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "CLN-3" "delete document" } else { Test-Fail "CLN-3" "delete document failed" }
    }
} catch { Test-Fail "CLN-3" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($kbId) {
        $r = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId" -Method Delete -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "CLN-4" "delete KB" } else { Test-Fail "CLN-4" "delete KB failed" }
    }
} catch { Test-Fail "CLN-4" "$($_.Exception.Message)" }

Write-Host ""
try {
    if ($configId) {
        $r = Invoke-RestMethod -Uri "$base/api/system/configs/$configId" -Method Delete -Headers @{Authorization="Bearer $token"}
        if ($r.code -eq 0) { Test-Pass "CLN-5" "delete test config" } else { Test-Fail "CLN-5" "delete test config failed" }
    }
} catch { Test-Fail "CLN-5" "$($_.Exception.Message)" }

# ==========================================
# Results
# ==========================================
$total = $pass + $fail
Write-Host "`n========================================" -ForegroundColor Yellow
Write-Host "  FINAL E2E TEST RESULTS" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  Total: $total" -ForegroundColor White
Write-Host "  Pass:  $pass" -ForegroundColor Green
Write-Host "  Fail:  $fail" -ForegroundColor Red
if ($total -gt 0) {
    Write-Host "  Rate:  $([math]::Round($pass/$total*100, 2))%" -ForegroundColor White
}
Write-Host "========================================" -ForegroundColor Yellow
if ($fail -eq 0) {
    Write-Host "`n  ALL TESTS PASSED!" -ForegroundColor Green
} else {
    Write-Host "`n  $fail TEST(S) FAILED!" -ForegroundColor Red
}