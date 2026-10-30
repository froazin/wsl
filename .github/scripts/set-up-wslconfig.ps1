# Writes the repository's .wslconfig to the runner's profile and shuts WSL down, because WSL only reads .wslconfig when its
# virtual machine starts.
param(
    [Parameter(Mandatory)] [string] $Path
)

$ErrorActionPreference = 'Stop'
$wsl = Join-Path $env:ProgramFiles 'WSL\wsl.exe'

function Fail([string] $Message) {
    Write-Output "::error title=.wslconfig::$Message"
    exit 1
}

& $wsl --version
if ($LASTEXITCODE -ne 0) { Fail "wsl.exe --version exited with $LASTEXITCODE." }

# processors and memory size the virtual machine for a workstation, not a runner, so WSL's defaults are kept for them.
# The runner doesn't support mirrored networking, and WSL falls back to none at all, so it keeps the default NAT.
$lines = Get-Content -LiteralPath $Path | Where-Object { $_ -notmatch '^\s*(processors|memory|networkingMode)\s*=' }
$target = Join-Path $env:USERPROFILE '.wslconfig'
Set-Content -LiteralPath $target -Value $lines
Write-Output "Wrote ${target}:"
Get-Content -LiteralPath $target

& $wsl --shutdown
if ($LASTEXITCODE -ne 0) { Fail "wsl.exe --shutdown exited with $LASTEXITCODE." }
