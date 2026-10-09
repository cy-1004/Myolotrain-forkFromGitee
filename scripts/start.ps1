# =====================================================================
# 启动 Myolotrain（Windows + Docker Desktop），宿主机端口被占用时自动顺延。
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts\start.ps1 [传给 docker compose up 的额外参数，例如 --build]
#
# 端口规则与 scripts/start.sh 一致：
#   1. 首选端口 = .env 中的 APP_PORT（默认 8000）；上次顺延过且 APP_PORT 没改时，优先复用 .app_port 记录的端口；
#   2. 被其他程序占用（包括 Hyper-V/WSL 保留的端口段）就 +1，最多尝试 APP_PORT_MAX_TRIES 个；
#      本服务自己的容器占着的端口不算冲突；
#   3. APP_PORT_STRICT=true 时不顺延，冲突直接报错；
#   4. 启动成功后打印实际访问地址，并等待服务就绪。
# 注意：本文件必须保存为 UTF-8 带 BOM，否则 Windows PowerShell 5.1 会按 GBK 解析中文导致语法错误。
# =====================================================================
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

function Get-Conf([string]$Key, [string]$Default) {
    $val = [Environment]::GetEnvironmentVariable($Key)
    if (-not $val -and (Test-Path .env)) {
        $line = Get-Content .env -Encoding UTF8 | Where-Object { $_ -match "^\s*$Key\s*=" } | Select-Object -Last 1
        if ($line) {
            $val = ($line -split '=', 2)[1] -replace '\s#.*$', ''
            $val = $val.Trim().Trim('"').Trim("'")
        }
    }
    if ($val) { return $val } else { return $Default }
}

function Test-Truthy([string]$Value) { return $Value -in @('true', '1', 'yes') }

# 调用 docker 等原生命令时临时放宽错误策略：Windows PowerShell 5.1 中，原生命令写到 stderr 的内容
# （docker compose 的进度信息都走 stderr）在 ErrorActionPreference=Stop 下会被当成终止性错误
function Invoke-Native([scriptblock]$Block) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Block } finally { $ErrorActionPreference = $old }
}

if (-not (Test-Path .env)) {
    Write-Error '缺少 .env。请先复制 .env.example 为 .env，并填写 SECRET_KEY、POSTGRES_PASSWORD'
}

$RequestedPort = [int](Get-Conf 'APP_PORT' '8000')
$MaxTries = [int](Get-Conf 'APP_PORT_MAX_TRIES' '20')
$Strict = Test-Truthy (Get-Conf 'APP_PORT_STRICT' 'false')
$UseGpu = Get-Conf 'USE_GPU' 'auto'
$WaitSeconds = [int](Get-Conf 'START_WAIT_SECONDS' '180')
$PortFile = '.app_port'

Invoke-Native { docker compose version *> $null }
if ($LASTEXITCODE -ne 0) { Write-Error '未找到 docker compose，请确认 Docker Desktop 已安装并启动' }

# GPU：Docker Desktop（WSL2 后端）只需要 Windows 侧装好 NVIDIA 驱动
$ComposeFiles = @('-f', 'docker-compose.yml')
$gpu = $false
if (Test-Truthy $UseGpu) { $gpu = $true }
elseif ($UseGpu -eq 'auto') {
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        Invoke-Native { nvidia-smi -L *> $null }
        $gpu = ($LASTEXITCODE -eq 0)
    }
}
if ($gpu) { $ComposeFiles += @('-f', 'docker-compose.gpu.yml'); Write-Host 'GPU：已启用' }
else { Write-Host 'GPU：未启用（未检测到 NVIDIA 驱动；训练将使用 CPU）' }

# 用真实 bind 判断端口是否可用：能同时发现"被占用"和"被 Hyper-V/WSL 保留"两种情况
function Test-PortFree([int]$Port) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
        $listener.Server.ExclusiveAddressUse = $true
        $listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($listener) { $listener.Stop() }
    }
}

# 本服务的容器当前占着的宿主机端口
$OwnPort = ''
$own = Invoke-Native { docker compose @ComposeFiles port app 8000 2>$null }
if ($LASTEXITCODE -eq 0 -and $own) { $OwnPort = (($own | Select-Object -First 1) -split ':')[-1].Trim() }

$LastRequested = ''; $LastActual = ''
if (Test-Path $PortFile) {
    $lines = @(Get-Content $PortFile)
    if ($lines.Count -ge 2) { $LastRequested = $lines[0].Trim(); $LastActual = $lines[1].Trim() }
}
if ($LastRequested -eq "$RequestedPort" -and $LastActual) { $StartPort = [int]$LastActual } else { $StartPort = $RequestedPort }
if ($Strict) { $StartPort = $RequestedPort; $MaxTries = 1 }

$port = $StartPort
$chosen = $null
for ($tries = 1; $tries -le $MaxTries; $tries++) {
    if ("$port" -ne $OwnPort -and -not (Test-PortFree $port)) {
        Write-Host "端口 $port 已被占用"
        $port++
        continue
    }
    Write-Host "使用端口 $port 启动..."
    $env:APP_PORT = "$port"
    $upArgs = $args
    # "$_" 把 5.1 中包装成 ErrorRecord 的 stderr 行还原成普通文本
    $out = Invoke-Native { docker compose @ComposeFiles up -d @upArgs 2>&1 | ForEach-Object { "$_" } | Out-String }
    $code = $LASTEXITCODE
    Write-Host $out
    if ($code -eq 0) { $chosen = $port; break }
    if ($out -match 'port is already allocated|address already in use|ports are not available|bind.*(failed|forbidden)|access a socket in a way forbidden') {
        if ($tries -lt $MaxTries) { Write-Host "端口 $port 绑定失败，尝试下一个" } else { Write-Host "端口 $port 绑定失败" }
        $port++
        continue
    }
    Write-Error '启动失败（非端口冲突），请检查上面的输出'
}

if (-not $chosen) {
    if ($Strict) { Write-Error "端口 $RequestedPort 已被占用，且 APP_PORT_STRICT=true 不允许顺延" }
    Write-Error "端口 $StartPort~$($StartPort + $MaxTries - 1) 全部被占用，请释放端口或调大 APP_PORT_MAX_TRIES"
}

Set-Content -Path $PortFile -Value @("$RequestedPort", "$chosen") -Encoding ASCII

# 优先取有默认网关的网卡地址：VMware/Hyper-V 等虚拟网卡没有网关，排在前面会给出同事访问不了的地址
$hostIp = (Get-NetIPConfiguration -ErrorAction SilentlyContinue |
    Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } |
    Select-Object -First 1).IPv4Address.IPAddress
if (-not $hostIp) {
    $hostIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and $_.PrefixOrigin -ne 'WellKnown' } |
        Select-Object -First 1).IPAddress
}
if (-not $hostIp) { $hostIp = 'localhost' }

Write-Host ('=' * 60)
if ($chosen -ne $RequestedPort -and $chosen -eq $StartPort) {
    Write-Host "注意：沿用上次顺延后的端口 $chosen（首选端口 $RequestedPort 当时被占用）" -ForegroundColor Yellow
    Write-Host "      如需改回首选端口，删除 $PortFile 后重新执行本脚本" -ForegroundColor Yellow
} elseif ($chosen -ne $RequestedPort) {
    Write-Host "注意：端口 $StartPort 被占用，本次使用端口 $chosen" -ForegroundColor Yellow
    Write-Host '      接口调用方和 PUBLIC_BASE_URL 需要使用新端口' -ForegroundColor Yellow
}
if ($LastActual -and $LastActual -ne "$chosen") { Write-Host "注意：端口与上次（$LastActual）不同" -ForegroundColor Yellow }
Write-Host "控制台:   http://${hostIp}:$chosen/"
Write-Host "健康检查: http://${hostIp}:$chosen/api/health"
Write-Host "实际端口已记录到 $PortFile"
Write-Host ('=' * 60)

if ($WaitSeconds -gt 0) {
    Write-Host -NoNewline '等待服务就绪'
    for ($waited = 0; $waited -lt $WaitSeconds; $waited += 2) {
        try {
            Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:$chosen/api/health" | Out-Null
            Write-Host ' 已就绪'
            exit 0
        } catch { Write-Host -NoNewline '.'; Start-Sleep -Seconds 2 }
    }
    Write-Host ''
    Write-Error "服务 $WaitSeconds 秒内未就绪，请查看日志：docker compose logs -f app"
}
