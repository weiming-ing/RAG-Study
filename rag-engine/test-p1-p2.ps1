# ============================================
# P1 Auth + P2 User/Role/Menu API Test (v2)
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

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  P1: Auth Module Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [1] Register
Write-Host "`n[1] POST /api/auth/register" -ForegroundColor Yellow
$body = '{"username":"testuser","password":"test123","displayName":"Test User"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/auth/register" -Method Post -Body $body -ContentType 'application/json'
    if ($resp.code -eq 0) { Test-Pass "register" "" } else { Test-Fail "register" "code=$($resp.code)" }
} catch { Test-Fail "register" "$($_.Exception.Message)" }

# [2] Duplicate - expect 400
Write-Host "`n[2] POST /api/auth/register - duplicate" -ForegroundColor Yellow
$body = '{"username":"testuser","password":"test123","displayName":"Test User"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/auth/register" -Method Post -Body $body -ContentType 'application/json'
    if ($resp.code -eq 400) { Test-Pass "duplicate register" "400" } else { Test-Fail "duplicate register" "expected 400, got $($resp.code)" }
} catch { Test-Fail "duplicate register" "$($_.Exception.Message)" }

# [3] Login
Write-Host "`n[3] POST /api/auth/login" -ForegroundColor Yellow
$body = '{"username":"admin","password":"admin123"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/auth/login" -Method Post -Body $body -ContentType 'application/json'
    $token = $resp.data.accessToken
    if ($resp.code -eq 0) { Test-Pass "login" "token=$($token.Substring(0,20))..." } else { Test-Fail "login" "code=$($resp.code)" }
} catch { Test-Fail "login" "$($_.Exception.Message)" }

# [4] Wrong password
Write-Host "`n[4] POST /api/auth/login - wrong password" -ForegroundColor Yellow
$body = '{"username":"admin","password":"wrong"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/auth/login" -Method Post -Body $body -ContentType 'application/json'
    Test-Fail "wrong password" "should have returned 401"
} catch { Test-Pass "wrong password" "401" }

# [5] /me
Write-Host "`n[5] GET /api/auth/me" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/auth/me" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "me" "user=$($resp.data.username)" } else { Test-Fail "me" "code=$($resp.code)" }
} catch { Test-Fail "me" "$($_.Exception.Message)" }

# [6] No auth
Write-Host "`n[6] GET /api/admin/users - no auth" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users" -Method Get
    Test-Fail "no auth" "should have returned 401"
} catch { Test-Pass "no auth" "401" }

# ============================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P2: User Management" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [7] List users
Write-Host "`n[7] GET /api/admin/users" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users?pageNum=1&pageSize=10" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "list users" "total=$($resp.data.total)" } else { Test-Fail "list users" "code=$($resp.code)" }
} catch { Test-Fail "list users" "$($_.Exception.Message)" }

# [8] Create user
Write-Host "`n[8] POST /api/admin/users" -ForegroundColor Yellow
$body = '{"username":"kbadmin","password":"kb123456","displayName":"KB Admin","email":"kb@test.com","status":1}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users" -Method Post -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    $newUserId = $resp.data.id
    if ($resp.code -eq 0) { Test-Pass "create user" "id=$newUserId" } else { Test-Fail "create user" "code=$($resp.code)" }
} catch { Test-Fail "create user" "$($_.Exception.Message)" }

# [9] Get user by id
Write-Host "`n[9] GET /api/admin/users/$newUserId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users/$newUserId" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "get user" "username=$($resp.data.username)" } else { Test-Fail "get user" "code=$($resp.code)" }
} catch { Test-Fail "get user" "$($_.Exception.Message)" }

# [10] Update user
Write-Host "`n[10] PUT /api/admin/users/$newUserId" -ForegroundColor Yellow
$body = '{"displayName":"KB Admin (Updated)","email":"kbadmin@test.com"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users/$newUserId" -Method Put -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "update user" "displayName=$($resp.data.displayName)" } else { Test-Fail "update user" "code=$($resp.code)" }
} catch { Test-Fail "update user" "$($_.Exception.Message)" }

# [11] Disable user
Write-Host "`n[11] PUT /api/admin/users/$newUserId/status - disable" -ForegroundColor Yellow
$body = '{"status":0}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users/$newUserId/status" -Method Put -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "disable user" "" } else { Test-Fail "disable user" "code=$($resp.code)" }
} catch { Test-Fail "disable user" "$($_.Exception.Message)" }

# [12] Enable user
Write-Host "`n[12] PUT /api/admin/users/$newUserId/status - enable" -ForegroundColor Yellow
$body = '{"status":1}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users/$newUserId/status" -Method Put -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "enable user" "" } else { Test-Fail "enable user" "code=$($resp.code)" }
} catch { Test-Fail "enable user" "$($_.Exception.Message)" }

# [13] Reset password
Write-Host "`n[13] PUT /api/admin/users/$newUserId/password" -ForegroundColor Yellow
$body = '{"password":"newpass123"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users/$newUserId/password" -Method Put -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "reset password" "" } else { Test-Fail "reset password" "code=$($resp.code)" }
} catch { Test-Fail "reset password" "$($_.Exception.Message)" }

# [14] Assign roles
Write-Host "`n[14] PUT /api/admin/users/$newUserId/roles" -ForegroundColor Yellow
$body = '{"roleIds":[2,3]}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users/$newUserId/roles" -Method Put -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "assign roles" "" } else { Test-Fail "assign roles" "code=$($resp.code)" }
} catch { Test-Fail "assign roles" "$($_.Exception.Message)" }

# [15] Delete user
Write-Host "`n[15] DELETE /api/admin/users/$newUserId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/users/$newUserId" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "delete user" "" } else { Test-Fail "delete user" "code=$($resp.code)" }
} catch { Test-Fail "delete user" "$($_.Exception.Message)" }

# ============================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P2: Role Management" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [16] List roles
Write-Host "`n[16] GET /api/admin/roles" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/roles" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "list roles" "count=$($resp.data.Count)" } else { Test-Fail "list roles" "code=$($resp.code)" }
} catch { Test-Fail "list roles" "$($_.Exception.Message)" }

# [17] Create role
Write-Host "`n[17] POST /api/admin/roles" -ForegroundColor Yellow
$body = '{"roleName":"Doc Auditor","roleCode":"ROLE_AUDITOR","description":"Can audit documents"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/roles" -Method Post -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    $roleId = $resp.data.id
    if ($resp.code -eq 0) { Test-Pass "create role" "id=$roleId" } else { Test-Fail "create role" "code=$($resp.code)" }
} catch { Test-Fail "create role" "$($_.Exception.Message)" }

# [18] Update role
Write-Host "`n[18] PUT /api/admin/roles/$roleId" -ForegroundColor Yellow
$body = '{"roleName":"Doc Auditor (Updated)","description":"Audit and edit docs"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/roles/$roleId" -Method Put -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "update role" "name=$($resp.data.roleName)" } else { Test-Fail "update role" "code=$($resp.code)" }
} catch { Test-Fail "update role" "$($_.Exception.Message)" }

# [19] Assign menus
Write-Host "`n[19] PUT /api/admin/roles/$roleId/menus" -ForegroundColor Yellow
$body = '{"menuIds":[1,3,31,32]}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/roles/$roleId/menus" -Method Put -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "assign menus" "" } else { Test-Fail "assign menus" "code=$($resp.code)" }
} catch { Test-Fail "assign menus" "$($_.Exception.Message)" }

# [20] Delete role
Write-Host "`n[20] DELETE /api/admin/roles/$roleId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/roles/$roleId" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "delete role" "" } else { Test-Fail "delete role" "code=$($resp.code)" }
} catch { Test-Fail "delete role" "$($_.Exception.Message)" }

# ============================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P2: Menu Management" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [21] Menu tree
Write-Host "`n[21] GET /api/admin/menus/tree" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/menus/tree" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "menu tree" "topLevel=$($resp.data.Count)" } else { Test-Fail "menu tree" "code=$($resp.code)" }
} catch { Test-Fail "menu tree" "$($_.Exception.Message)" }

# [22] User menus
Write-Host "`n[22] GET /api/admin/menus/user" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/menus/user" -Method Get -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "user menus" "count=$($resp.data.Count)" } else { Test-Fail "user menus" "code=$($resp.code)" }
} catch { Test-Fail "user menus" "$($_.Exception.Message)" }

# [23] Create menu
Write-Host "`n[23] POST /api/admin/menus" -ForegroundColor Yellow
$body = '{"parentId":2,"menuName":"Audit Log","menuType":"MENU","path":"/system/audit","component":"system/AuditLog","permissionCode":"system:audit:view","sortOrder":4}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/menus" -Method Post -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    $menuId = $resp.data.id
    if ($resp.code -eq 0) { Test-Pass "create menu" "id=$menuId" } else { Test-Fail "create menu" "code=$($resp.code)" }
} catch { Test-Fail "create menu" "$($_.Exception.Message)" }

# [24] Update menu
Write-Host "`n[24] PUT /api/admin/menus/$menuId" -ForegroundColor Yellow
$body = '{"menuName":"Operation Audit Log","icon":"DocumentChecked"}'
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/menus/$menuId" -Method Put -Body $body -ContentType 'application/json' -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "update menu" "name=$($resp.data.menuName)" } else { Test-Fail "update menu" "code=$($resp.code)" }
} catch { Test-Fail "update menu" "$($_.Exception.Message)" }

# [25] Delete menu
Write-Host "`n[25] DELETE /api/admin/menus/$menuId" -ForegroundColor Yellow
try {
    $resp = Invoke-RestMethod -Uri "$base/api/admin/menus/$menuId" -Method Delete -Headers @{Authorization="Bearer $token"}
    if ($resp.code -eq 0) { Test-Pass "delete menu" "" } else { Test-Fail "delete menu" "code=$($resp.code)" }
} catch { Test-Fail "delete menu" "$($_.Exception.Message)" }

# ============================================
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  P1+P2 Results: $pass/$($pass+$fail) passed" -ForegroundColor $(if($fail -eq 0){'Green'}else{'Red'})
Write-Host "========================================" -ForegroundColor Cyan