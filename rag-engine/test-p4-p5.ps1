# ============================================
# P4 Knowledge Base + P5 Document API Test
# ============================================
$base = "http://localhost:8002"
$pass = 0; $fail = 0

function Test-Pass($name, $detail) {
    $script:pass++
    Write-Host "  PASS: $name $detail" -ForegroundColor Green
}
function Test-Fail($name, $detail) {
    $script:fail++
    Write-Host "  FAIL: $name $detail" -ForegroundColor Red
}

# ==========================================
# Login as admin
# ==========================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Login as admin" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$body = '{"username":"admin","password":"admin123"}'
$resp = Invoke-RestMethod -Uri "$base/api/auth/login" -Method Post -Body $body -ContentType 'application/json'
$token = $resp.data.accessToken
Write-Host "  Token: $($token.Substring(0,20))..." -ForegroundColor Gray

# ==========================================
# P4: Knowledge Base Management
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P4: Knowledge Base Management" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [1] List knowledge bases
Write-Host "`n[1] GET /api/knowledge-bases" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases?pageNum=1&pageSize=10" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "list KBs" "total=$($resp.data.total)" } else { Test-Fail "list KBs" "code=$($resp.code)" }
} catch { Test-Fail "list KBs" "$($_.Exception.Message)" }

# [2] Create knowledge base
Write-Host "`n[2] POST /api/knowledge-bases" -ForegroundColor Yellow
$kbBody = '{"name":"Test KB","description":"Test knowledge base for API testing","category":"tech","tags":"test,api","department":"tech","isPublic":1}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases" -Method Post -Body $kbBody -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    $kbId = $resp.data.id
    if ($resp.code -eq 0) { Test-Pass "create KB" "id=$kbId" } else { Test-Fail "create KB" "code=$($resp.code)" }
} catch { Test-Fail "create KB" "$($_.Exception.Message)" }

# [3] Get KB by id
Write-Host "`n[3] GET /api/knowledge-bases/$kbId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "get KB" "name=$($resp.data.name)" } else { Test-Fail "get KB" "code=$($resp.code)" }
} catch { Test-Fail "get KB" "$($_.Exception.Message)" }

# [4] Update KB
Write-Host "`n[4] PUT /api/knowledge-bases/$kbId" -ForegroundColor Yellow
$kbBody2 = '{"name":"Test KB (Updated)","description":"Updated description","category":"tech","tags":"test,api,updated","department":"tech","isPublic":1}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId" -Method Put -Body $kbBody2 -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "update KB" "name=$($resp.data.name)" } else { Test-Fail "update KB" "code=$($resp.code)" }
} catch { Test-Fail "update KB" "$($_.Exception.Message)" }

# [5] Update KB config
Write-Host "`n[5] PUT /api/knowledge-bases/$kbId/config" -ForegroundColor Yellow
$configBody = '{"chunkSize":500,"overlap":80,"topK":10,"vectorWeight":0.7,"bm25Weight":0.3,"minScore":0.5}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId/config" -Method Put -Body $configBody -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "update KB config" "" } else { Test-Fail "update KB config" "code=$($resp.code)" }
} catch { Test-Fail "update KB config" "$($_.Exception.Message)" }

# [6] Update KB status (disable)
Write-Host "`n[6] PUT /api/knowledge-bases/$kbId/status - disable" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId/status?status=DISABLED" -Method Put -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "disable KB" "" } else { Test-Fail "disable KB" "code=$($resp.code)" }
} catch { Test-Fail "disable KB" "$($_.Exception.Message)" }

# [7] Update KB status (enable)
Write-Host "`n[7] PUT /api/knowledge-bases/$kbId/status - enable" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId/status?status=ACTIVE" -Method Put -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "enable KB" "" } else { Test-Fail "enable KB" "code=$($resp.code)" }
} catch { Test-Fail "enable KB" "$($_.Exception.Message)" }

# [8] Grant access to user
Write-Host "`n[8] POST /api/knowledge-bases/$kbId/users" -ForegroundColor Yellow
$accessBody = '{"userIds":[4],"accessLevel":"EDITOR"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId/users" -Method Post -Body $accessBody -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "grant access" "" } else { Test-Fail "grant access" "code=$($resp.code)" }
} catch { Test-Fail "grant access" "$($_.Exception.Message)" }

# [9] Get authorized users
Write-Host "`n[9] GET /api/knowledge-bases/$kbId/users" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId/users" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "get KB users" "count=$($resp.data.Count)" } else { Test-Fail "get KB users" "code=$($resp.code)" }
} catch { Test-Fail "get KB users" "$($_.Exception.Message)" }

# [10] Revoke access
Write-Host "`n[10] DELETE /api/knowledge-bases/$kbId/users/4" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId/users/4" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "revoke access" "" } else { Test-Fail "revoke access" "code=$($resp.code)" }
} catch { Test-Fail "revoke access" "$($_.Exception.Message)" }

# ==========================================
# P5: Document Management
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P5: Document Management" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [11] List documents
Write-Host "`n[11] GET /api/knowledge/$kbId/documents" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents?pageNum=1&pageSize=10" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "list documents" "total=$($resp.data.total)" } else { Test-Fail "list documents" "code=$($resp.code)" }
} catch { Test-Fail "list documents" "$($_.Exception.Message)" }

# [12] Manual create document
Write-Host "`n[12] POST /api/knowledge/$kbId/documents/manual" -ForegroundColor Yellow
$manualBody = '{"title":"Manual Test Doc","content":"This is a manually created test document for API testing purposes. It contains sample text about knowledge management and RAG architecture.","tags":"manual,test"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/manual" -Method Post -Body $manualBody -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    $docId = $resp.data.id
    if ($resp.code -eq 0) { Test-Pass "manual create doc" "id=$docId" } else { Test-Fail "manual create doc" "code=$($resp.code)" }
} catch { Test-Fail "manual create doc" "$($_.Exception.Message)" }

# [13] Get document by id
Write-Host "`n[13] GET /api/knowledge/$kbId/documents/$docId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "get document" "name=$($resp.data.fileName)" } else { Test-Fail "get document" "code=$($resp.code)" }
} catch { Test-Fail "get document" "$($_.Exception.Message)" }

# [14] Update document
Write-Host "`n[14] PUT /api/knowledge/$kbId/documents/$docId" -ForegroundColor Yellow
$updateBody = '{"fileName":"Manual Test Doc (Updated)","tags":"manual,test,updated"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId" -Method Put -Body $updateBody -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "update document" "name=$($resp.data.fileName)" } else { Test-Fail "update document" "code=$($resp.code)" }
} catch { Test-Fail "update document" "$($_.Exception.Message)" }

# [15] Reparse document
Write-Host "`n[15] POST /api/knowledge/$kbId/documents/$docId/reparse" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId/reparse" -Method Post -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "reparse document" "" } else { Test-Fail "reparse document" "code=$($resp.code)" }
} catch { Test-Fail "reparse document" "$($_.Exception.Message)" }

# [16] Get document chunks
Write-Host "`n[16] GET /api/knowledge/$kbId/documents/$docId/chunks" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId/chunks" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "get chunks" "count=$($resp.data.Count)" } else { Test-Fail "get chunks" "code=$($resp.code)" }
} catch { Test-Fail "get chunks" "$($_.Exception.Message)" }

# [17] Get parse tasks
Write-Host "`n[17] GET /api/knowledge/$kbId/documents/$docId/tasks" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId/tasks" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "get tasks" "count=$($resp.data.Count)" } else { Test-Fail "get tasks" "code=$($resp.code)" }
} catch { Test-Fail "get tasks" "$($_.Exception.Message)" }

# [18] Soft delete document
Write-Host "`n[18] DELETE /api/knowledge/$kbId/documents/$docId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "soft delete doc" "" } else { Test-Fail "soft delete doc" "code=$($resp.code)" }
} catch { Test-Fail "soft delete doc" "$($_.Exception.Message)" }

# [19] Restore document
Write-Host "`n[19] POST /api/knowledge/$kbId/documents/$docId/restore" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId/restore" -Method Post -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "restore document" "" } else { Test-Fail "restore document" "code=$($resp.code)" }
} catch { Test-Fail "restore document" "$($_.Exception.Message)" }

# [20] Purge (hard delete) document
Write-Host "`n[20] DELETE /api/knowledge/$kbId/documents/$docId/purge" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$docId/purge" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "purge document" "" } else { Test-Fail "purge document" "code=$($resp.code)" }
} catch { Test-Fail "purge document" "$($_.Exception.Message)" }

# ==========================================
# P5: File Upload Test
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P5: File Upload Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Create temp file
$tempFile = [System.IO.Path]::GetTempFileName() + ".txt"
"RAG (Retrieval-Augmented Generation) is a technique that enhances LLM responses by retrieving relevant information from a knowledge base before generating an answer.`n`nThe process involves three main steps:`n1. Document Ingestion: Documents are uploaded, parsed, and split into chunks.`n2. Vector Embedding: Each chunk is converted into a vector embedding using an embedding model.`n3. Retrieval: When a query comes in, the system retrieves the most relevant chunks and feeds them to the LLM along with the query.`n`nThis approach significantly improves the accuracy and relevance of AI-generated responses by grounding them in factual data." | Out-File -FilePath $tempFile -Encoding UTF8

# [21] Upload document
Write-Host "`n[21] POST /api/knowledge/$kbId/documents/upload" -ForegroundColor Yellow
try {
    $fileBytes = [System.IO.File]::ReadAllBytes($tempFile)
    $boundary = [System.Guid]::NewGuid().ToString()
    $LF = "`r`n"
    $bodyLines = @()
    $bodyLines += "--$boundary"
    $bodyLines += "Content-Disposition: form-data; name=`"file`"; filename=`"test_doc.txt`""
    $bodyLines += "Content-Type: text/plain$LF"
    $bodyLines += [System.Text.Encoding]::UTF8.GetString($fileBytes)
    $bodyLines += "--$boundary"
    $bodyLines += "Content-Disposition: form-data; name=`"tags`"$LF"
    $bodyLines += "uploaded,test"
    $bodyLines += "--$boundary--"
    $bodyContent = $bodyLines -join $LF
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyContent)
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/upload" -Method Post -Body $bodyBytes -ContentType "multipart/form-data; boundary=$boundary" -Headers @{Authorization="Bearer $token"}
    $uploadDocId = $resp.data.id
    if ($resp.code -eq 0) { Test-Pass "upload document" "id=$uploadDocId" } else { Test-Fail "upload document" "code=$($resp.code)" }
} catch { Test-Fail "upload document" "$($_.Exception.Message)" }

# [22] Reparse uploaded document
Write-Host "`n[22] POST /api/knowledge/$kbId/documents/$uploadDocId/reparse" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$uploadDocId/reparse" -Method Post -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "reparse uploaded doc" "" } else { Test-Fail "reparse uploaded doc" "code=$($resp.code)" }
} catch { Test-Fail "reparse uploaded doc" "$($_.Exception.Message)" }

# [23] Purge uploaded document
Write-Host "`n[23] DELETE /api/knowledge/$kbId/documents/$uploadDocId/purge" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge/$kbId/documents/$uploadDocId/purge" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "purge uploaded doc" "" } else { Test-Fail "purge uploaded doc" "code=$($resp.code)" }
} catch { Test-Fail "purge uploaded doc" "$($_.Exception.Message)" }

# Clean up temp file
Remove-Item $tempFile -Force -ErrorAction SilentlyContinue

# ==========================================
# P?: Internal API Tests
# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P?: Internal API Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [24] Knowledge statistics
Write-Host "`n[24] GET /api/internal/knowledge/statistics" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/internal/knowledge/statistics" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "knowledge stats" "totalDocs=$($resp.data.totalDocuments)" } else { Test-Fail "knowledge stats" "code=$($resp.code)" }
} catch { Test-Fail "knowledge stats" "$($_.Exception.Message)" }

# [25] Search
Write-Host "`n[25] POST /api/internal/search" -ForegroundColor Yellow
$searchBody = '{"query":"RAG retrieval augmented generation","topK":5,"enableHybrid":true}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/internal/search" -Method Post -Body $searchBody -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "search" "results=$($resp.data.totalResults)" } else { Test-Fail "search" "code=$($resp.code)" }
} catch { Test-Fail "search" "$($_.Exception.Message)" }

# [26] Delete KB (cleanup)
Write-Host "`n[26] DELETE /api/knowledge-bases/$kbId (cleanup)" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/knowledge-bases/$kbId" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "delete KB" "" } else { Test-Fail "delete KB" "code=$($resp.code)" }
} catch { Test-Fail "delete KB" "$($_.Exception.Message)" }

# ==========================================
Write-Host "`n========================================" -ForegroundColor Cyan
if ($fail -eq 0) {
    Write-Host "  P4+P5 Results: $pass/$($pass+$fail) passed" -ForegroundColor Green
} else {
    Write-Host "  P4+P5 Results: $pass/$($pass+$fail) passed" -ForegroundColor Red
}
Write-Host "========================================" -ForegroundColor Cyan