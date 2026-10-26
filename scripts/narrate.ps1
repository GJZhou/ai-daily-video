<# Prepare the pinned portable runtime if needed, then run the offline voice generator. #>
[CmdletBinding()]
param([switch]$Check, [string]$TextFile, [string]$Output, [string]$BundleDirectory)
$ErrorActionPreference = 'Stop'
if (-not $Check -and (-not $TextFile -or -not $Output)) { throw 'Provide -TextFile and -Output, or use -Check.' }
$skillRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifest = Get-Content -LiteralPath (Join-Path $skillRoot 'references/portable-runtime.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$python = Join-Path $skillRoot ('.runtime/' + $manifest.runtime_id + '/python/python.exe')
if (-not (Test-Path -LiteralPath $python)) {
    $installerArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'install-runtime.ps1'))
    if ($BundleDirectory) { $installerArgs += @('-BundleDirectory', $BundleDirectory) }
    & powershell.exe @installerArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$voiceArgs = @('-X', 'utf8', '-I', '-B', (Join-Path $PSScriptRoot 'narrate.py'))
if ($Check) { $voiceArgs += '--check' } else {
    if (-not $TextFile -or -not $Output) { throw 'Provide -TextFile and -Output, or use -Check.' }
    $voiceArgs += @('--text-file', $TextFile, '--output', $Output)
}
& $python @voiceArgs
exit $LASTEXITCODE
