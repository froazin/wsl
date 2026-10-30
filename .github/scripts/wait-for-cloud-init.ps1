# Starts the instance for the first time, waits for cloud-init, shows its logs and fails on any error or recoverable error.
param(
    [Parameter(Mandatory)] [string] $Instance
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$wsl = Join-Path $env:ProgramFiles 'WSL\wsl.exe'
$failed = $false

function Report([string] $Level, [string] $Message) {
    Write-Output "::${Level} title=cloud-init::$Message"
    if ($Level -eq 'error') { $script:failed = $true }
}

# -e runs the command without a shell, so its arguments reach it as they are.
function InInstance {
    & $wsl -d $Instance -u root -e @args
}

# The first command boots the instance, and systemd starts cloud-init with the seed in place. Running a command as root
# skips the distribution's first-run setup. One wsl.exe process for the whole wait keeps a client attached, so WSL doesn't
# stop the instance as idle.
InInstance cloud-init status --wait
$waited = $LASTEXITCODE

Write-Output '::group::cloud-init status'
InInstance cloud-init status --long
Write-Output '::endgroup::'
Write-Output '::group::Warnings and errors in cloud-init.log'
InInstance grep -E 'WARNING|ERROR|Traceback' /var/log/cloud-init.log
Write-Output '::endgroup::'
Write-Output '::group::cloud-init-output.log'
InInstance tail -n 500 /var/log/cloud-init-output.log
Write-Output '::endgroup::'

# cloud-init status exits 1 for an error and 2 for a recoverable error. The recoverable errors are judged one by one below.
if ($waited -ne 0 -and $waited -ne 2) { Report error "cloud-init status --wait exited with $waited." }

# result.json is written when cloud-init's last stage finishes. It leaves recoverable errors out, so status adds them.
$result = (InInstance cat /var/lib/cloud/data/result.json) -join "`n"
if ($LASTEXITCODE -ne 0 -or -not $result) {
    Report error 'cloud-init wrote no result.json, so it never finished.'
} else {
    $v1 = ($result | ConvertFrom-Json).v1
    Write-Output "Datasource: $($v1.datasource)"
    if ($v1.datasource -notmatch 'WSL') { Report error "cloud-init used $($v1.datasource), not the WSL datasource." }
    foreach ($e in @($v1.errors)) { if ($e) { Report error $e } }
}

# Recoverable errors every instance built from this config gets, which are logged rather than reported. The user-data is a
# Jinja template, not plain cloud-config, so cloud-init waits for the network at the start of its network stage by
# starting systemd-networkd-wait-online.service, which Ubuntu's WSL image masks (observed).
$expected = @(
    'Failed to wait for network: (?s).*systemd-networkd-wait-online\.service is masked'
)

$status = (InInstance cloud-init status --format json) -join "`n" | ConvertFrom-Json
foreach ($e in @($status.errors)) { if ($e) { Report error $e } }
if ($status.recoverable_errors) {
    foreach ($level in $status.recoverable_errors.PSObject.Properties) {
        # cloud-init can list the same error more than once.
        foreach ($e in @($level.Value) | Where-Object { $_ } | Select-Object -Unique) {
            if (@($expected | Where-Object { $e -match $_ }).Count -gt 0) {
                Write-Output "Expected recoverable $($level.Name), not reported: $(($e -split "`n")[0])"
            } else {
                Report error "Recoverable $($level.Name): $e"
            }
        }
    }
}
if ($waited -eq 2 -and -not $status.recoverable_errors) {
    Report error 'cloud-init status --wait exited with 2, but cloud-init status lists no recoverable errors.'
}

if ($failed) { exit 1 }
Write-Output "cloud-init finished: $($status.extended_status)"
# The runner exits with $LASTEXITCODE, which is cloud-init status's 2 when only expected errors are left.
exit 0
