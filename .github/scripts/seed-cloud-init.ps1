# Puts the user-data and a filled-in copy of the meta-data template in %USERPROFILE%\.cloud-init, named after the instance,
# as the README tells users to.
param(
    [Parameter(Mandatory)] [string] $Instance,
    [Parameter(Mandatory)] [string] $UserData,
    [Parameter(Mandatory)] [string] $MetaData,
    [string] $Username = '',
    [string] $GitName = '',
    [string] $GitEmail = ''
)

$ErrorActionPreference = 'Stop'

function Fail([string] $Message) {
    Write-Output "::error title=cloud-init seed::$Message"
    exit 1
}

$seed = Join-Path $env:USERPROFILE '.cloud-init'
New-Item -ItemType Directory -Force -Path $seed | Out-Null

# Fill in the template's empty keys, the way a user would, so its defaults are tested too.
$meta = (Get-Content -Raw -LiteralPath $MetaData) -replace "`r`n", "`n"
$values = [ordered]@{ username = $Username; git_name = $GitName; git_email = $GitEmail }
foreach ($key in $values.Keys) {
    $value = $values[$key]
    if (-not $value) { continue }
    $pattern = "(?m)^$([regex]::Escape($key)):[ \t]*$"
    if ($meta -notmatch $pattern) { Fail "$MetaData has no empty $key to fill in." }
    # Single-quoted YAML, with quotes doubled, so the value is read as written.
    $line = "${key}: '" + $value.Replace("'", "''") + "'"
    $meta = [regex]::Replace($meta, $pattern, { param($match) $line })
}

$userTarget = Join-Path $seed "$Instance.user-data"
$metaTarget = Join-Path $seed "$Instance.meta-data"
Copy-Item -LiteralPath $UserData -Destination $userTarget
[IO.File]::WriteAllText($metaTarget, $meta)

Write-Output "Wrote $userTarget and ${metaTarget}:"
Write-Output $meta
