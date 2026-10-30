# Runs check-instance.sh as root inside the instance, from the checkout.
param(
    [Parameter(Mandatory)] [string] $Instance
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$wsl = Join-Path $env:ProgramFiles 'WSL\wsl.exe'

# The user and git name reach the script through WSLENV, so wsl.exe never has to quote them.
$env:WSLENV = (@($env:WSLENV, 'E2E_USER', 'E2E_GIT_NAME') | Where-Object { $_ }) -join ':'

& $wsl -d $Instance -u root --cd $PWD.Path -e sh .github/scripts/check-instance.sh
if ($LASTEXITCODE -ne 0) {
    Write-Output "::error title=Instance check::check-instance.sh exited with $LASTEXITCODE."
    exit 1
}
