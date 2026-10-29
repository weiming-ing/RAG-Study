#!/usr/bin/env pwsh
<#
.SYNOPSIS
  联网侧：构建并打包「RAG 助手」离线交付镜像包。

.DESCRIPTION
  客户内网无法访问 Docker Hub / PyPI / Maven Central，因此镜像必须在可联网的
  机器上构建完成后整体交付。本脚本完成：

    1. 预检（Docker daemon、compose、磁盘空间）
    2. 构建 3 个应用镜像（frontend / backend / rag-engine）
    3. 拉取 3 个基础镜像（mysql / redis / qdrant）
    4. 一次性 docker save 为单个 tar
    5. 附带 compose、env 模板、初始化 SQL、安装脚本
    6. 生成 manifest.json（含镜像 ID 与 digest）与 SHA256SUMS

  产出的 dist 目录整体拷给客户，在客户侧执行 install.sh 即可。

.PARAMETER Version
  版本号，用于产物命名（默认取当前时间）。

.PARAMETER OutDir
  产物目录，默认 deploy/offline/dist（已加入 .gitignore）。

.PARAMETER SkipBuild
  跳过 docker compose build，直接用本地已有镜像打包。

.PARAMETER Compress
  额外生成 .tar.gz（体积更小，但压缩 5GB+ 很慢）。

.EXAMPLE
  pwsh -File deploy/offline/build-images.ps1 -Version 1.0.0

.EXAMPLE
  pwsh -File deploy/offline/build-images.ps1 -SkipBuild -Compress
#>
[CmdletBinding()]
param(
    [string]$Version = (Get-Date -Format 'yyyyMMdd-HHmm'),
    [string]$OutDir = (Join-Path $PSScriptRoot 'dist'),
    [switch]$SkipBuild,
    [switch]$Compress
)

$ErrorActionPreference = 'Stop'

$RepoRoot    = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ComposeFile = Join-Path $RepoRoot 'docker-compose.yml'

function Write-Step  { param($m) Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Write-Ok    { param($m) Write-Host "  [OK] $m"   -ForegroundColor Green }
function Write-Warn2 { param($m) Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Fail        { param($m) Write-Host "  [FAIL] $m" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 1. 预检
Write-Step '1/7 预检'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail '未找到 docker 命令' }
docker version --format '{{.Server.Version}}' 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail 'Docker daemon 未运行，请先启动 Docker Desktop / dockerd' }
Write-Ok "Docker 已就绪"
docker compose version 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail '未找到 docker compose（v2）插件' }
Write-Ok 'docker compose 已就绪'
if (-not (Test-Path -LiteralPath $ComposeFile)) { Fail "找不到 $ComposeFile" }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$freeGB = [math]::Round((Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($OutDir).TrimEnd(':\'))).Free / 1GB, 1)
if ($freeGB -lt 20) { Write-Warn2 "产物目录所在盘剩余 ${freeGB}GB，镜像包通常 4-8GB，建议先清理" }
else { Write-Ok "磁盘剩余 ${freeGB}GB" }

# ---------------------------------------------------------- 2. 解析镜像清单
Write-Step '2/7 解析镜像清单（与 docker-compose.yml 保持一致）'
Push-Location $RepoRoot
$images = @(docker compose config --images 2>$null)
Pop-Location
if ($LASTEXITCODE -ne 0 -or $images.Count -eq 0) { Fail '无法从 compose 解析镜像清单' }
$images | ForEach-Object { Write-Host "  - $_" }
foreach ($img in $images) {
    if ($img -match ':latest$') {
        Write-Warn2 "$img 使用 latest 标签，交付不可复现；建议固定版本后重新打包"
    }
}

# ---------------------------------------------------------------- 3. 构建
Write-Step '3/7 构建应用镜像'
if ($SkipBuild) {
    Write-Warn2 '已指定 -SkipBuild，跳过构建，直接使用本地镜像'
} else {
    Push-Location $RepoRoot
    docker compose build
    $buildExit = $LASTEXITCODE
    Pop-Location
    if ($buildExit -ne 0) { Fail 'docker compose build 失败' }
    Write-Ok '应用镜像构建完成'
}

# ------------------------------------------------------- 4. 拉取基础镜像
Write-Step '4/7 拉取基础镜像'
foreach ($img in $images) {
    docker pull $img 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Ok "已拉取 $img" }
    else { Write-Warn2 "跳过 $img（应为本地构建的应用镜像）" }
}

# ------------------------------------------------- 5. 校验并记录镜像信息
Write-Step '5/7 校验镜像并记录 ID / digest'
$records = @()
foreach ($img in $images) {
    $id = (docker image inspect $img --format '{{.Id}}' 2>$null)
    if (-not $id) { Fail "镜像不存在，构建或拉取可能失败: $img" }
    $digest = ''
    $d = (docker image inspect $img --format '{{range .RepoDigests}}{{println .}}{{end}}' 2>$null)
    if ($d) { $digest = ($d | Select-Object -First 1).Trim() }
    $records += [pscustomobject]@{ name = $img; id = $id; digest = $digest }
    Write-Host ("  {0,-24} {1}" -f $img, $id.Substring(0, 19))
}

# ------------------------------------------------------------ 6. 导出与组装
Write-Step '6/7 导出镜像并组装交付包'
$imgDir = Join-Path $OutDir 'images'
New-Item -ItemType Directory -Force -Path $imgDir | Out-Null
$tarName = "rag-assistant-images-$Version.tar"
$tarPath = Join-Path $imgDir $tarName

Write-Host "  正在导出镜像（体积较大，请耐心等待）..."
docker save -o $tarPath @images
if ($LASTEXITCODE -ne 0) { Fail 'docker save 失败（磁盘空间是否足够？）' }
$tarSizeGB = [math]::Round((Get-Item -LiteralPath $tarPath).Length / 1GB, 2)
Write-Ok "镜像包已生成: $tarName (${tarSizeGB}GB)"

# 组装交付包所需文件（保持 compose 依赖的相对路径结构）
$copies = @(
    @{ src = 'docker-compose.yml';                 dst = 'docker-compose.yml' },
    @{ src = '.env.example';                       dst = 'env.example' },
    @{ src = 'docker\mysql\init.sql';              dst = 'docker\mysql\init.sql' },
    @{ src = 'deploy\offline\install.sh';          dst = 'install.sh' },
    @{ src = 'deploy\offline\README.md';           dst = 'README.md' },
    @{ src = 'deploy\nginx\rag-assistant.conf';    dst = 'reference\rag-assistant.conf' },
    @{ src = 'rag-admin\nginx.conf';               dst = 'reference\rag-admin-nginx.conf' }
)
foreach ($c in $copies) {
    $srcPath = Join-Path $RepoRoot $c.src
    $dstPath = Join-Path $OutDir   $c.dst
    if (-not (Test-Path -LiteralPath $srcPath)) { Write-Warn2 "缺少 $($c.src)，跳过"; continue }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dstPath) | Out-Null
    Copy-Item -LiteralPath $srcPath -Destination $dstPath -Force
    Write-Host "  + $($c.dst)"
}

$gitCommit = ''
try { $gitCommit = (git -C $RepoRoot rev-parse HEAD 2>$null) } catch { }

$manifest = [pscustomobject]@{
    product     = 'rag-assistant'
    version     = $Version
    builtAt     = (Get-Date).ToString('s')
    builtOn     = $env:COMPUTERNAME
    gitCommit   = $gitCommit
    imageTar    = "images/$tarName"
    imageTarSha256 = (Get-FileHash -LiteralPath $tarPath -Algorithm SHA256).Hash
    images      = $records
    notes       = @(
        '客户侧执行 ./install.sh 完成离线安装',
        '镜像 ID 用于客户侧校验，digest 用于追溯基础镜像来源',
        '若镜像包超过 4GB，建议先完成 P0-3（后端镜像瘦身）再交付'
    )
}
$manifestPath = Join-Path $OutDir 'manifest.json'
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Ok '已生成 manifest.json'

# 校验和文件
$sumLines = @()
Get-ChildItem -LiteralPath $OutDir -Recurse -File |
    Where-Object { $_.Name -ne 'SHA256SUMS' } |
    ForEach-Object {
        $rel = $_.FullName.Substring($OutDir.Length).TrimStart('\') -replace '\\', '/'
        $sumLines += "$((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower())  $rel"
    }
Set-Content -LiteralPath (Join-Path $OutDir 'SHA256SUMS') -Value $sumLines -Encoding ASCII
Write-Ok "已生成 SHA256SUMS（$($sumLines.Count) 个文件）"

if ($Compress) {
    Write-Host '  正在压缩（较慢）...'
    Push-Location $OutDir
    tar -czf "rag-assistant-offline-$Version.tar.gz" .
    $compressExit = $LASTEXITCODE
    Pop-Location
    if ($compressExit -eq 0) { Write-Ok "已生成 rag-assistant-offline-$Version.tar.gz" }
    else { Write-Warn2 '压缩失败（可忽略，tar 包本身已可用）' }
}

# ---------------------------------------------------------------- 7. 汇总
Write-Step '7/7 完成'
$totalGB = [math]::Round(((Get-ChildItem -LiteralPath $OutDir -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1GB), 2)
Write-Host "  产物目录 : $OutDir"
Write-Host "  总大小   : ${totalGB}GB"
Write-Host "  镜像 tar : $tarName"
Write-Host ''
Write-Host '  交付步骤：'
Write-Host '    1) 将整个 dist 目录拷贝到客户机器（U 盘 / 内网文件服务器）'
Write-Host '    2) 客户侧执行: chmod +x install.sh && ./install.sh'
Write-Host '    3) install.sh 会自动校验 SHA256SUMS、加载镜像、生成 .env、启动并自检'
Write-Host ''
Write-Warn2 '交付前务必修改初始管理员密码（admin/admin123），见 README.md'
