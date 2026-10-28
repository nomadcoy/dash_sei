$ErrorActionPreference = "Stop"

$mutex = New-Object System.Threading.Mutex($false, "Global\GestaoVistaTunel")
if (-not $mutex.WaitOne(0)) {
    Write-Output "Ja existe um supervisor do tunel em execucao; saindo."
    exit 0
}

$proj = Split-Path -Parent $PSScriptRoot
Set-Location $proj

$port = 8599
$ct = "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code-tunnel.exe"
$url = "https://whnk7638-$port.brs.devtunnels.ms"
$logDir = Join-Path $proj "data\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$urlFile = Join-Path $proj "data\tunel_url.txt"
$erroLog = Join-Path $logDir "tunel_err.log"
$hostLog = Join-Path $logDir "tunel_host.log"
$portasFile = Join-Path $proj "data\portas_tunel.json"

if (-not (Test-Path $ct)) {
    Write-Output "FALHA: code-tunnel.exe nao encontrado em $ct"
    exit 1
}

$json = (Get-Content $portasFile -Raw -EA SilentlyContinue)
if (-not $json) { $json = '[{"number":8599,"privacy":"public","protocol":"http"}]' }
$json = $json.Trim()

function EsperaDashboard {
    for ($i = 0; $i -lt 30; $i++) {
        if (Get-NetTCPConnection -LocalPort 8599 -State Listen -EA SilentlyContinue) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function MatarHosts {
    Get-CimInstance Win32_Process -Filter "Name='code-tunnel.exe'" -EA SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
}

if (-not (EsperaDashboard)) {
    Add-Content $erroLog "Aviso: dashboard (8599) nao respondeu em 60s; seguindo. $(Get-Date -Format s)" -EA SilentlyContinue
}

MatarHosts
Start-Sleep -Seconds 2

$backoff = 15

while ($true) {
    $iniciou = Get-Date
    try {
        MatarHosts
        Start-Sleep -Seconds 1
        & $ct tunnel prune 2>&1 | Out-Null

        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $ct
        $psi.Arguments = 'tunnel forward-internal --provider github'
        $psi.UseShellExecute = $false
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.CreateNoWindow = $true

        $p = New-Object System.Diagnostics.Process
        $p.StartInfo = $psi
        $p.Start() | Out-Null

        $outTask = $p.StandardOutput.ReadToEndAsync()
        $errTask = $p.StandardError.ReadToEndAsync()

        Start-Sleep -Seconds 12
        $p.StandardInput.WriteLine($json)
        $p.StandardInput.Flush()

        Start-Sleep -Seconds 8
        if ($p.HasExited) {
            Add-Content $erroLog "processo saiu cedo (exit $($p.ExitCode)) em $(Get-Date -Format s)" -EA SilentlyContinue
            Add-Content $hostLog "--- saiu cedo (exit $($p.ExitCode)) $(Get-Date -Format s) ---" -EA SilentlyContinue
            Add-Content $hostLog $errTask.Result -EA SilentlyContinue
            Add-Content $hostLog $outTask.Result -EA SilentlyContinue
            Start-Sleep -Seconds $backoff
            $backoff = [Math]::Min($backoff * 2, 180)
            continue
        }

        @("url=$url", "porta=$port", "pid=$($p.Id)", "atualizado=$((Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))") |
            Set-Content $urlFile -Encoding UTF8
        Add-Content $erroLog "tunel ativo pid $($p.Id) em $(Get-Date -Format s)" -EA SilentlyContinue

        while (-not $p.HasExited) { Start-Sleep -Seconds 10 }

        $dur = [int]((Get-Date) - $iniciou).TotalSeconds
        Add-Content $erroLog "tunel caiu apos ${dur}s (exit $($p.ExitCode)) em $(Get-Date -Format s); reiniciando" -EA SilentlyContinue
        Add-Content $hostLog "--- saiu apos ${dur}s (exit $($p.ExitCode)) $(Get-Date -Format s) ---" -EA SilentlyContinue
        Add-Content $hostLog $errTask.Result -EA SilentlyContinue
        Add-Content $hostLog $outTask.Result -EA SilentlyContinue

        if ($dur -lt 120) {
            $backoff = [Math]::Min($backoff * 2, 180)
        } else {
            $backoff = 15
        }
    } catch {
        Add-Content $erroLog "erro: $_ em $(Get-Date -Format s)" -EA SilentlyContinue
    }
    Start-Sleep -Seconds $backoff
}