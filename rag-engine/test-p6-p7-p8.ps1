# P6+P7+P8 Test Script - Chunk/Vector, Debug, Conversation, Audit
param($base = "http://localhost:8002")

$pass = 0; $fail = 0; $docId = $null; $chunkId = $null; $chunkId2 = $null; $caseId = $null; $convId = $null
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

# Create KB for testing
$kbBody = '{"name":"P6 Test KB","description":"Test KB for P6/P7/P8","category":"test"}'
$kbResp = Invoke-RestMethod -Uri "$base/api/knowledge-bases" -Method Post -Body $kbBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
$kbId = $kbResp.data.id
Write-Host "  KB created: $kbId"

# Create a document for testing
$manualBody = '{"title":"P6 Test Doc","content":"Spring Boot is a Java framework for building microservices. It provides auto-configuration, embedded servers, and production-ready features. Spring Boot makes it easy to create stand-alone, production-grade Spring based Applications. The framework follows convention over configuration principle. It integrates seamlessly with Spring Cloud for distributed systems.","department":"' + $kbId + '","category":"test"}'
$docResp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/manual" -Method Post -Body $manualBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
$docId = $docResp.data.id
Write-Host "  Document created: $docId"

# Wait for document processing to complete
Write-Host "  Waiting for chunking to complete..."
$maxRetries = 10
$retryCount = 0
do {
    Start-Sleep -Seconds 1
    $retryCount++
    try {
        $chunkCheck = Invoke-RestMethod -Uri "$base/api/chunks?documentId=$docId" -Headers @{Authorization="Bearer $token"}
        $ready = ($chunkCheck.code -eq 0 -and $chunkCheck.data.total -gt 0)
    } catch { $ready = $false }
} while (-not $ready -and $retryCount -lt $maxRetries)
if ($ready) { Write-Host "  Chunks ready: $($chunkCheck.data.total)" -ForegroundColor Green }
else { Write-Host "  Warning: No chunks found after $maxRetries retries" -ForegroundColor Yellow }

# ==========================================
# P6: Chunk & Vector Management
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P6: Chunk & Vector Management" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [1] List chunks
Write-Host "`n[1] GET /api/chunks" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/chunks?pageNum=1&pageSize=20" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "list chunks" "total=$($resp.data.total)" } else { Test-Fail "list chunks" "code=$($resp.code)" }
} catch { Test-Fail "list chunks" "$($_.Exception.Message)" }

# [2] List chunks by document
Write-Host "`n[2] GET /api/chunks?documentId=$docId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/chunks?documentId=$docId" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0 -and $resp.data.total -gt 0) {
        $chunkId = $resp.data.records[0].chunkId
        if ($resp.data.total -ge 2) { $chunkId2 = $resp.data.records[1].chunkId }
        Test-Pass "list doc chunks" "total=$($resp.data.total), chunkId=$chunkId"
    } else { Test-Fail "list doc chunks" "total=$($resp.data.total)" }
} catch { Test-Fail "list doc chunks" "$($_.Exception.Message)" }

# [3] Get chunk by ID
Write-Host "`n[3] GET /api/chunks/$chunkId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/chunks/$chunkId" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "get chunk" "content=$($resp.data.content.Substring(0,[Math]::Min(40,$resp.data.content.Length)))" } else { Test-Fail "get chunk" "code=$($resp.code)" }
} catch { Test-Fail "get chunk" "$($_.Exception.Message)" }

# [4] Update chunk content
Write-Host "`n[4] PUT /api/chunks/$chunkId" -ForegroundColor Yellow
try {
    $updateBody = '{"content":"Updated chunk content for testing purposes"}'
    $resp = Invoke-RestMethod -Uri "$base/api/chunks/$chunkId" -Method Put -Body $updateBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "update chunk" "success" } else { Test-Fail "update chunk" "code=$($resp.code)" }
} catch { Test-Fail "update chunk" "$($_.Exception.Message)" }

# [5] Re-vectorize chunk
Write-Host "`n[5] POST /api/chunks/$chunkId/revectorize" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/chunks/$chunkId/revectorize" -Method Post -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "revectorize chunk" "success" } else { Test-Fail "revectorize chunk" "code=$($resp.code)" }
} catch { Test-Fail "revectorize chunk" "$($_.Exception.Message)" }

# [6] Split chunk
Write-Host "`n[6] POST /api/chunks/$chunkId/split" -ForegroundColor Yellow
try {
    $splitBody = '{"position":20}'
    $resp = Invoke-RestMethod -Uri "$base/api/chunks/$chunkId/split" -Method Post -Body $splitBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "split chunk" "newId=$($resp.data.chunkId)" } else { Test-Fail "split chunk" "code=$($resp.code)" }
} catch { Test-Fail "split chunk" "$($_.Exception.Message)" }

# [7] Merge chunks (need 2 chunks)
Write-Host "`n[7] POST /api/chunks/merge" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/chunks?documentId=$docId" -Headers @{Authorization="Bearer $token"}
    if ($resp.data.records.Count -ge 2) {
        $c1 = $resp.data.records[0].chunkId
        $c2 = $resp.data.records[1].chunkId
        $mergeBody = '{"chunkId1":"' + $c1 + '","chunkId2":"' + $c2 + '"}'
        $mergeResp = Invoke-RestMethod -Uri "$base/api/chunks/merge" -Method Post -Body $mergeBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
        if ($mergeResp.code -eq 0) {
            $chunkId = $mergeResp.data.chunkId
            Test-Pass "merge chunks" "mergedId=$chunkId"
        } else { Test-Fail "merge chunks" "code=$($mergeResp.code)" }
    } else { Test-Pass "merge chunks" "skipped(need 2 chunks)" }
} catch { Test-Fail "merge chunks" "$($_.Exception.Message)" }

# [8] Vector sync status
Write-Host "`n[8] GET /api/chunks/sync-status" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/chunks/sync-status" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "sync status" "docs=$($resp.data.totalDocuments), chunks=$($resp.data.totalChunks)" } else { Test-Fail "sync status" "code=$($resp.code)" }
} catch { Test-Fail "sync status" "$($_.Exception.Message)" }

# [9] Rebuild KB vectors
Write-Host "`n[9] POST /api/chunks/rebuild/$kbId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/chunks/rebuild/$kbId" -Method Post -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "rebuild vectors" "success" } else { Test-Fail "rebuild vectors" "code=$($resp.code)" }
} catch { Test-Fail "rebuild vectors" "$($_.Exception.Message)" }

# [10] Delete chunk
Write-Host "`n[10] DELETE /api/chunks/$chunkId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/chunks/$chunkId" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "delete chunk" "success" } else { Test-Fail "delete chunk" "code=$($resp.code)" }
} catch { Test-Fail "delete chunk" "$($_.Exception.Message)" }

# ==========================================
# P7: Debug Workbench
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P7: Debug Workbench" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [11] Debug search
Write-Host "`n[11] POST /api/debug/search" -ForegroundColor Yellow
try {
    $debugBody = '{"query":"Spring Boot framework","topK":5,"enableHybrid":true,"similarityThreshold":0.0,"vectorWeight":0.7,"keywordWeight":0.3}'
    $resp = Invoke-RestMethod -Uri "$base/api/debug/search" -Method Post -Body $debugBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "debug search" "results=$($resp.data.results.Count)" } else { Test-Fail "debug search" "code=$($resp.code)" }
} catch { Test-Fail "debug search" "$($_.Exception.Message)" }

# [12] Create test case
Write-Host "`n[12] POST /api/debug/test-cases" -ForegroundColor Yellow
try {
    $caseBody = '{"name":"Test Case 1","queryText":"What is Spring Boot?","topK":5,"similarityThreshold":0.3,"enableHybrid":1,"vectorWeight":0.7,"keywordWeight":0.3,"kbId":"' + $kbId + '","tags":"test,spring"}'
    $resp = Invoke-RestMethod -Uri "$base/api/debug/test-cases" -Method Post -Body $caseBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $caseId = $resp.data.id
    if ($resp.code -eq 0) { Test-Pass "create test case" "id=$caseId" } else { Test-Fail "create test case" "code=$($resp.code)" }
} catch { Test-Fail "create test case" "$($_.Exception.Message)" }

# [13] List test cases
Write-Host "`n[13] GET /api/debug/test-cases" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/debug/test-cases" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "list test cases" "total=$($resp.data.total)" } else { Test-Fail "list test cases" "code=$($resp.code)" }
} catch { Test-Fail "list test cases" "$($_.Exception.Message)" }

# [14] Get test case
Write-Host "`n[14] GET /api/debug/test-cases/$caseId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/debug/test-cases/$caseId" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "get test case" "name=$($resp.data.name)" } else { Test-Fail "get test case" "code=$($resp.code)" }
} catch { Test-Fail "get test case" "$($_.Exception.Message)" }

# [15] Update test case
Write-Host "`n[15] PUT /api/debug/test-cases/$caseId" -ForegroundColor Yellow
try {
    $updateBody = '{"name":"Test Case 1 (Updated)","queryText":"What is Spring Boot?","topK":10,"similarityThreshold":0.5,"enableHybrid":1,"vectorWeight":0.8,"keywordWeight":0.2,"kbId":"' + $kbId + '","tags":"test,spring,updated"}'
    $resp = Invoke-RestMethod -Uri "$base/api/debug/test-cases/$caseId" -Method Put -Body $updateBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "update test case" "name=$($resp.data.name)" } else { Test-Fail "update test case" "code=$($resp.code)" }
} catch { Test-Fail "update test case" "$($_.Exception.Message)" }

# [16] Run all test cases
Write-Host "`n[16] POST /api/debug/test-cases/run-all" -ForegroundColor Yellow
try {
    $runBody = '{"kbId":"' + $kbId + '"}'
    $resp = Invoke-RestMethod -Uri "$base/api/debug/test-cases/run-all" -Method Post -Body $runBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "run all test cases" "total=$($resp.data.total), passed=$($resp.data.passed)" } else { Test-Fail "run all test cases" "code=$($resp.code)" }
} catch { Test-Fail "run all test cases" "$($_.Exception.Message)" }

# [17] Delete test case
Write-Host "`n[17] DELETE /api/debug/test-cases/$caseId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/debug/test-cases/$caseId" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "delete test case" "success" } else { Test-Fail "delete test case" "code=$($resp.code)" }
} catch { Test-Fail "delete test case" "$($_.Exception.Message)" }

# ==========================================
# P8: Conversation Logs
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P8: Conversation Logs" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [18] Create conversation log
Write-Host "`n[18] POST /api/conversations" -ForegroundColor Yellow
try {
    $convBody = '{"sessionId":"test-session-001","userId":1,"question":"What is Spring Boot?","answer":"Spring Boot is a Java framework for building microservices.","referencedChunks":"[]","kbId":"' + $kbId + '","status":"SUCCESS","feedback":0,"latencyMs":350,"tokenCount":120}'
    $resp = Invoke-RestMethod -Uri "$base/api/conversations" -Method Post -Body $convBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    $convId = $resp.data.id
    if ($resp.code -eq 0) { Test-Pass "create conversation" "id=$convId" } else { Test-Fail "create conversation" "code=$($resp.code)" }
} catch { Test-Fail "create conversation" "$($_.Exception.Message)" }

# [19] List conversations
Write-Host "`n[19] GET /api/conversations" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/conversations" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "list conversations" "total=$($resp.data.total)" } else { Test-Fail "list conversations" "code=$($resp.code)" }
} catch { Test-Fail "list conversations" "$($_.Exception.Message)" }

# [20] Get conversation by ID
Write-Host "`n[20] GET /api/conversations/$convId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/conversations/$convId" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "get conversation" "question=$($resp.data.question.Substring(0,[Math]::Min(30,$resp.data.question.Length)))" } else { Test-Fail "get conversation" "code=$($resp.code)" }
} catch { Test-Fail "get conversation" "$($_.Exception.Message)" }

# [21] Update feedback - like
Write-Host "`n[21] PUT /api/conversations/$convId/feedback (like)" -ForegroundColor Yellow
try {
    $fbBody = '{"feedback":1,"reason":"","comment":"Good answer"}'
    $resp = Invoke-RestMethod -Uri "$base/api/conversations/$convId/feedback" -Method Put -Body $fbBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "feedback like" "success" } else { Test-Fail "feedback like" "code=$($resp.code)" }
} catch { Test-Fail "feedback like" "$($_.Exception.Message)" }

# [22] Update feedback - dislike
Write-Host "`n[22] PUT /api/conversations/$convId/feedback (dislike)" -ForegroundColor Yellow
try {
    $fbBody = '{"feedback":-1,"reason":"MISSING_DATA","comment":"Missing details"}'
    $resp = Invoke-RestMethod -Uri "$base/api/conversations/$convId/feedback" -Method Put -Body $fbBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "feedback dislike" "success" } else { Test-Fail "feedback dislike" "code=$($resp.code)" }
} catch { Test-Fail "feedback dislike" "$($_.Exception.Message)" }

# [23] Feedback stats
Write-Host "`n[23] GET /api/conversations/stats/feedback" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/conversations/stats/feedback" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "feedback stats" "count=$($resp.data.Count)" } else { Test-Fail "feedback stats" "code=$($resp.code)" }
} catch { Test-Fail "feedback stats" "$($_.Exception.Message)" }

# [24] Recent stats
Write-Host "`n[24] GET /api/conversations/stats/recent" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/conversations/stats/recent?days=7" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "recent stats" "conversations=$($resp.data.totalConversations)" } else { Test-Fail "recent stats" "code=$($resp.code)" }
} catch { Test-Fail "recent stats" "$($_.Exception.Message)" }

# [25] Filter conversations by keyword
Write-Host "`n[25] GET /api/conversations?keyword=Spring" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/conversations?keyword=Spring" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "filter conversations" "total=$($resp.data.total)" } else { Test-Fail "filter conversations" "code=$($resp.code)" }
} catch { Test-Fail "filter conversations" "$($_.Exception.Message)" }

# ==========================================
# P8: Audit Logs
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P8: Audit Logs" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Trigger some audit events
try {
    Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/manual" -Method Post -Body $manualBody -ContentType "application/json" -Headers @{Authorization="Bearer $token"} | Out-Null
} catch { }

# [26] List audit logs
Write-Host "`n[26] GET /api/audit-logs" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/audit-logs" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "list audit logs" "total=$($resp.data.total)" } else { Test-Fail "list audit logs" "code=$($resp.code)" }
} catch { Test-Fail "list audit logs" "$($_.Exception.Message)" }

# [27] Filter audit logs by operation
Write-Host "`n[27] GET /api/audit-logs?operation=UPLOAD" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/audit-logs?operation=UPLOAD" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "filter audit logs" "total=$($resp.data.total)" } else { Test-Fail "filter audit logs" "code=$($resp.code)" }
} catch { Test-Fail "filter audit logs" "$($_.Exception.Message)" }

# [28] Operation stats
Write-Host "`n[28] GET /api/audit-logs/stats/operations" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/audit-logs/stats/operations?days=7" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "operation stats" "count=$($resp.data.Count)" } else { Test-Fail "operation stats" "code=$($resp.code)" }
} catch { Test-Fail "operation stats" "$($_.Exception.Message)" }

# [29] Daily stats
Write-Host "`n[29] GET /api/audit-logs/stats/daily" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/audit-logs/stats/daily?days=7" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "daily stats" "count=$($resp.data.Count)" } else { Test-Fail "daily stats" "code=$($resp.code)" }
} catch { Test-Fail "daily stats" "$($_.Exception.Message)" }

# [30] Filter audit logs by keyword
Write-Host "`n[30] GET /api/audit-logs?keyword=test" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/audit-logs?keyword=test" -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "filter by keyword" "total=$($resp.data.total)" } else { Test-Fail "filter by keyword" "code=$($resp.code)" }
} catch { Test-Fail "filter by keyword" "$($_.Exception.Message)" }

# Cleanup
Write-Host "`n[Cleanup] Deleting KB..." -ForegroundColor DarkGray
try {
    Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId" -Method Delete -Headers @{Authorization="Bearer $token"} | Out-Null
} catch { }

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P6+P7+P8 Results: $pass/30 passed" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Red" })
Write-Host "========================================" -ForegroundColor Cyan