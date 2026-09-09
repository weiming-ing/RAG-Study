# =============================================================================
# RAG 助手 — Python 多实例启动脚本
# =============================================================================
param(
    [int]Count = 3,
    [switch]Stop = false,
    [string]BaseDir = (Resolve-Path "PSScriptRoot\..\backend")
)

instances = @(
    @{ Port = 8001; Name = "main" }
    @{ Port = 8011; Name = "worker-1" }
    @{ Port = 8012; Name = "worker-2" }
    @{ Port = 8013; Name = "worker-3" }
    @{ Port = 8014; Name = "worker-4" }
)

function Start-Instances {
    Write-Host "启动 Count 个 Python 后端实例..." -ForegroundColor Yellow
    activeCount = [Math]::Min(Count, instances.Count)
    for (i = 0; i -lt activeCount; i++) {
        inst = instances[i]
        logFile = "BaseDir\..\logs\python-(inst.Name)-(inst.Port).log"
        logDir = Split-Path logFile -Parent
        if (!(Test-Path logDir)) { New-Item -ItemType Directory -Path logDir -Force | Out-Null }
        env:PORT = inst.Port
        env:UVICORN_RELOAD = "false"
        Write-Host "  [(i+1)/activeCount] 启动实例 (inst.Name) -> 端口 (inst.Port)"
        psi = New-Object System.Diagnostics.ProcessStartInfo
        psi.FileName = "python"
        psi.Arguments = "-u main.py"
        psi.WorkingDirectory = BaseDir
        psi.UseShellExecute = false
        psi.RedirectStandardOutput = true
        psi.RedirectStandardError = true
        psi.EnvironmentVariables["PORT"] = inst.Port.ToString()
        psi.EnvironmentVariables["UVICORN_RELOAD"] = "false"
        p = [System.Diagnostics.Process]::Start(psi)
        p | Export-Clixml -Path "BaseDir\..\logs\.pid-(inst.Port).xml"
        Start-Sleep -Seconds 1
    }
    Write-Host "所有实例已启动！" -ForegroundColor Cyan
}

function Stop-Instances {
    Write-Host "正在停止所有 Python 实例..." -ForegroundColor Yellow
    Get-ChildItem "BaseDir\..\logs\.pid-*.xml" -ErrorAction SilentlyContinue | ForEach-Object {
        try { p = Import-Clixml _.FullName; if (!p.HasExited) { p.Kill() }; Remove-Item _.FullName -Force } catch {}
    }
    Write-Host "所有实例已停止" -ForegroundColor Cyan
}

if (Stop) { Stop-Instances } else { Start-Instances }
