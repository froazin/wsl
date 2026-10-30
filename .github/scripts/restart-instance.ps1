# Restarts the instance, as the README tells users to, and checks systemd starts cleanly with what cloud-init set up.
param(
    [Parameter(Mandatory)] [string] $Instance
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$wsl = Join-Path $env:ProgramFiles 'WSL\wsl.exe'

& $wsl --terminate $Instance
if ($LASTEXITCODE -ne 0) {
    Write-Output "::error title=Restart::wsl.exe --terminate $Instance exited with $LASTEXITCODE."
    exit 1
}

# Collect the output before picking a line: Select-Object -Last stops wsl.exe early, and then $LASTEXITCODE isn't set.
$output = & $wsl -d $Instance -u root -e systemctl is-system-running --wait
$state = "$($output | Select-Object -Last 1)".Trim()
Write-Output "systemd is $state."
if ($state -ne 'running') {
    & $wsl -d $Instance -u root -e systemctl --failed --no-pager
    Write-Output "::error title=Restart::systemd is '$state', not running."
    exit 1
}
