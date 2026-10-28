$ErrorActionPreference = "Stop"
New-NetFirewallRule -DisplayName "GestaoVista Dash 8599" -Direction Inbound -Protocol TCP -LocalPort 8599 -Action Allow -Profile Any | Out-Null
Get-NetFirewallRule -DisplayName "GestaoVista Dash 8599" |
    Select-Object DisplayName, Enabled, Direction, Action
Get-NetFirewallPortFilter -AssociatedNetFirewallRule (Get-NetFirewallRule -DisplayName "GestaoVista Dash 8599") |
    Select-Object Protocol, LocalPort