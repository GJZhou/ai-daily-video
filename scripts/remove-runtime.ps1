<# Remove only the versioned portable runtime owned by this Skill; no original project files. #>
[CmdletBinding()]
param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
$skillRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifest = Get-Content -LiteralPath (Join-Path $skillRoot 'references/portable-runtime.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.runtime_id -notmatch '^win-x64-[a-zA-Z0-9-]+$') { throw 'Invalid runtime identifier.' }
$runtimeRoot = [IO.Path]::GetFullPath((Join-Path $skillRoot '.runtime'))
$target = [IO.Path]::GetFullPath((Join-Path $runtimeRoot $manifest.runtime_id))
if (-not $target.StartsWith(($runtimeRoot + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe removal path.' }
$cursor = $target
while ($cursor) {
    if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Refusing removal through linked paths.' }
    $cursor = [IO.Path]::GetDirectoryName($cursor)
}
if (-not (Test-Path -LiteralPath $target)) { Write-Output 'Runtime absent; nothing to remove.'; exit 0 }
$receipt = Get-Content -LiteralPath (Join-Path $target 'install-receipt.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($receipt.owner -ne 'ai-daily-video/install-runtime.ps1' -or $receipt.runtime_id -ne $manifest.runtime_id) { throw 'Unrecognized runtime ownership; nothing deleted.' }
Get-ChildItem -LiteralPath $target -Recurse -Force | ForEach-Object { if ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked descendant detected; nothing deleted.' } }
Write-Output "Remove portable runtime only: $target"
if (-not $DryRun) { Remove-Item -LiteralPath $target -Recurse -Force }
