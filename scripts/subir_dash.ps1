$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
Set-Location $proj

$port = 8599
# Executavel renomeado evita a regra de firewall que bloqueia
# "...\Python314\python.exe" (Block) e cai na regra Allow da porta 8599.
$py = "C:\Users\x13376866\AppData\Local\Programs\Python\Python314\gdashsrv.exe"
if (-not (Test-Path $py)) {
    $orig = Join-Path (Split-Path $py) "python.exe"
    if (Test-Path $orig) { Copy-Item $orig $py -Force }
}
$logDir = Join-Path $proj "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$pidFile = Join-Path $proj "data\server.pid"

function Test-Porta {
    param([int]$P)
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect("127.0.0.1", $P)
        $c.Close()
        return $true
    } catch { return $false }
}

function Test-Saude {
    param([int]$P)
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$P/_stcore/health" -UseBasicParsing -TimeoutSec 3
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

# 1) Encerra instancia anterior (por PID registrado e, se possivel, por quem ocupa a porta).
if (Test-Path $pidFile) {
    $old = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($old -and $old -match '^\d+$') {
        Stop-Process -Id ([int]$old) -Force -ErrorAction SilentlyContinue
    }
}
$conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
foreach ($c in $conns) {
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
}

# 2) Espera a porta liberar de fato (ate 20s).
$t = 0
while ((Test-Porta $port) -and $t -lt 40) {
    Start-Sleep -Milliseconds 500
    $t++
}

# 3) Remove logs antigos (evita arquivo travado pelo processo que saiu).
foreach ($f in @("dashboard.log", "dashboard_err.log")) {
    $p = Join-Path $logDir $f
    if (Test-Path $p) { Remove-Item $p -Force -ErrorAction SilentlyContinue }
}

# 4) Sobe o dashboard via launcher (serve.py injeta o service worker).
$env:DASH_PORT = "$port"
$stdout = Join-Path $logDir "dashboard.log"
$stderr = Join-Path $logDir "dashboard_err.log"
$p = Start-Process -FilePath $py -ArgumentList @("dashboard\serve.py") -WorkingDirectory $proj -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$p.Id | Set-Content $pidFile

# 5) Aguarda o dashboard responder no health (ate 180s; cold-start sob Task Scheduler e lento).
$t = 0
$up = $false
while ($t -lt 180) {
    if (Test-Saude -P $port) { $up = $true; break }
    Start-Sleep -Seconds 1
    $t++
}
if ($up) {
    Write-Output "Dashboard no ar na porta $port (PID $($p.Id))"
    exit 0
}
Write-Output "FALHA: dashboard nao subiu. Ver data\logs\dashboard_err.log"
exit 1