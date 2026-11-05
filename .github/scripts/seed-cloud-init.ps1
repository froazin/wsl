# Puts the user-data and a filled-in copy of the README's meta-data example in %USERPROFILE%\.cloud-init, named after the
# instance, as the README tells users to.
param(
    [Parameter(Mandatory)] [string] $Instance,
    [Parameter(Mandatory)] [string] $UserData,
    [Parameter(Mandatory)] [string] $Readme,
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

# The yaml code block straight after the marker comment, which META_DATA_EXAMPLE_MARKER in scripts/build/config.py also
# names, so invoke validate checks the same example.
$text = (Get-Content -Raw -LiteralPath $Readme) -replace "`r`n", "`n"
$example = [regex]::Match($text, '(?ms)^<!-- meta-data example -->\n+```yaml\n(.*?)^```$')
if (-not $example.Success) { Fail "$Readme has no yaml code block straight after <!-- meta-data example -->." }

# Fill in the example's empty keys, the way a user would, so its defaults are tested too. invoke validate checks the
# example leaves these keys empty, through META_DATA_FILLED_KEYS in scripts/build/config.py.
$meta = $example.Groups[1].Value
$values = [ordered]@{ username = $Username; git_name = $GitName; git_email = $GitEmail }
foreach ($key in $values.Keys) {
    $value = $values[$key]
    if (-not $value) { continue }
    $pattern = "(?m)^$([regex]::Escape($key)):[ \t]*$"
    if ($meta -notmatch $pattern) { Fail "The meta-data example in $Readme has no empty $key to fill in." }
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
