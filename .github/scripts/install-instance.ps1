# Installs the distribution as the README does, but without starting it, so the next step's command is its first boot.
param(
    [Parameter(Mandatory)] [string] $Instance
)

$ErrorActionPreference = 'Stop'
$wsl = Join-Path $env:ProgramFiles 'WSL\wsl.exe'

& $wsl --install $Instance --no-launch --web-download
if ($LASTEXITCODE -ne 0) {
    Write-Output "::error title=Install::wsl.exe --install $Instance exited with $LASTEXITCODE."
    exit 1
}

& $wsl --list --verbose
