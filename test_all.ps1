@"
=== Test 1: Health Check ===
"@
Write-Host "=== Test 1: Health Check ==="
try {
    $r = Invoke-RestMethod -Uri http://localhost:8002/api/internal/health -Method Get
    Write-Host "PASS: status=$($r.data.status), service=$($r.data.service)"
} catch {
    Write-Host "FAIL: $_"
}

Write-Host ""
Write-Host "=== Test 2: Upload Document ==="
try {
    $form = @{
        file = Get-Item -Path "D:\RAG-study\test_doc.txt"
        department = "医疗"
        category = "AI应用"
    }
    $r = Invoke-RestMethod -Uri http://localhost:8002/api/internal/knowledge/upload -Method Post -Form $form
    Write-Host "PASS: code=$($r.code), docId=$($r.data.id), fileName=$($r.data.fileName), status=$($r.data.status)"
    $docId = $r.data.id
} catch {
    Write-Host "FAIL: $_"
    $docId = $null
}

Write-Host ""
Write-Host "=== Test 3: Document List ==="
try {
    $r = Invoke-RestMethod -Uri "http://localhost:8002/api/internal/knowledge/list?pageNum=1&pageSize=20" -Method Get
    Write-Host "PASS: code=$($r.code), total=$($r.data.total), pages=$($r.data.pages)"
    if ($r.data.records) {
        foreach ($doc in $r.data.records) {
            Write-Host "  - id=$($doc.id), name=$($doc.fileName), status=$($doc.status), chunks=$($doc.totalChunks)"
        }
    }
} catch {
    Write-Host "FAIL: $_"
}

Write-Host ""
Write-Host "=== Test 4: Statistics ==="
try {
    $r = Invoke-RestMethod -Uri http://localhost:8002/api/internal/knowledge/statistics -Method Get
    Write-Host "PASS: code=$($r.code)"
    Write-Host "  totalDocs=$($r.data.totalDocs), totalChunks=$($r.data.totalChunks), indexedDocs=$($r.data.indexedDocs)"
} catch {
    Write-Host "FAIL: $_"
}

Write-Host ""
Write-Host "=== Test 5: Search (Basic) ==="
try {
    $body = @{
        query = "深度学习在医学影像分析中的应用"
        topK = 5
        enableHybrid = $true
    } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri http://localhost:8002/api/internal/search -Method Post -Body $body -ContentType "application/json"
    Write-Host "PASS: code=$($r.code), totalHits=$($r.data.totalHits), latency=$($r.data.latency)s"
    if ($r.data.results) {
        $i = 1
        foreach ($res in $r.data.results) {
            Write-Host "  [$i] score=$($res.score), content=$($res.content.Substring(0, [Math]::Min(80, $res.content.Length)))..."
            $i++
        }
    }
} catch {
    Write-Host "FAIL: $_"
}

Write-Host ""
Write-Host "=== Test 6: Search with Rerank ==="
try {
    $body = @{
        query = "Transformer在电子病历中的应用"
        topK = 3
        enableHybrid = $true
        rerankTopK = 10
    } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri http://localhost:8002/api/internal/search/rerank -Method Post -Body $body -ContentType "application/json"
    Write-Host "PASS: code=$($r.code), totalHits=$($r.data.totalHits), latency=$($r.data.latency)s"
    if ($r.data.results) {
        $i = 1
        foreach ($res in $r.data.results) {
            Write-Host "  [$i] score=$($res.score), content=$($res.content.Substring(0, [Math]::Min(80, $res.content.Length)))..."
            $i++
        }
    }
} catch {
    Write-Host "FAIL: $_"
}

Write-Host ""
Write-Host "=== Test 7: Multi-hop Search ==="
try {
    $body = @{
        query = "人工智能如何帮助医生进行疾病诊断"
        topK = 5
        enableHybrid = $true
    } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri http://localhost:8002/api/internal/search/multihop -Method Post -Body $body -ContentType "application/json"
    Write-Host "PASS: code=$($r.code), totalHits=$($r.data.totalHits), latency=$($r.data.latency)s"
    if ($r.data.results) {
        $i = 1
        foreach ($res in $r.data.results) {
            Write-Host "  [$i] score=$($res.score), content=$($res.content.Substring(0, [Math]::Min(80, $res.content.Length)))..."
            $i++
        }
    }
} catch {
    Write-Host "FAIL: $_"
}

Write-Host ""
Write-Host "=== Test 8: Delete Document ==="
if ($docId) {
    try {
        $r = Invoke-RestMethod -Uri "http://localhost:8002/api/internal/knowledge/$docId" -Method Delete
        Write-Host "PASS: code=$($r.code), message=$($r.message)"
    } catch {
        Write-Host "FAIL: $_"
    }
} else {
    Write-Host "SKIP: No document to delete"
}

Write-Host ""
Write-Host "=== ALL TESTS COMPLETE ==="