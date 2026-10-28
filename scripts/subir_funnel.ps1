$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
Set-Location $proj

$port = 8599
$ts = "C:\Program Files\Tailscale\tailscale.exe"
$urlFile = Join-Path $proj "data\tunel_url.txt"

if (-not (Test-Path $ts)) {
    Write-Output "FALHA: tailscale.exe nao encontrado em $ts"
    exit 1
}

# --bg deixa o funnel persistente (sobrevive a reinicios enquanto o Tailscale roda).
$ErrorActionPreference = "Continue"
$out = (& $ts funnel --bg $port) 2>&1 | Out-String
$ErrorActionPreference = "Stop"

$m = [regex]::Match($out, "https://[^\s]+\.ts\.net[^\s]*")
if (-not $m.Success) {
    Write-Output "FALHA: nao obtive a URL do funnel"
    Write-Output $out
    exit 1
}
$url = $m.Value.Trim().TrimEnd('/')
@(
    "url=$url"
    "porta=$port"
    "atualizado=$((Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))"
) | Set-Content $urlFile -Encoding UTF8
Write-Output "Funnel no ar: $url"
exit 0
