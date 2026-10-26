<# Install a checksum-pinned, application-local Windows x64 voice runtime. #>
[CmdletBinding()]
param(
    [string]$BundleDirectory,
    [switch]$CheckOnly,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$skillRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifest = Get-Content -LiteralPath (Join-Path $skillRoot 'references/portable-runtime.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { throw 'Windows 10/11 x64 is required.' }
if ($manifest.runtime_id -notmatch '^win-x64-[a-zA-Z0-9-]+$') { throw 'Invalid runtime identifier.' }
$runtimeRoot = Join-Path $skillRoot '.runtime'
$target = Join-Path $runtimeRoot $manifest.runtime_id
function Assert-PlainPath([string]$Path) {
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked path is not allowed: $cursor" }
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}
function Assert-Hash([string]$Path, [string]$Expected) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { $actual = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $hasher.Dispose() }
    if ($actual -ne $Expected) { throw "Checksum mismatch: $([IO.Path]::GetFileName($Path))" }
}
function Receive-ReleaseFile([string]$Name, [string]$Destination) {
    if ($BundleDirectory) {
        $source = Join-Path $BundleDirectory $Name
        Assert-PlainPath $source
        Copy-Item -LiteralPath $source -Destination $Destination
        return
    }
    if ($manifest.download_base -ne ('https://github.com/GJZhou/ai-daily-video/releases/download/' + $manifest.release_tag + '/')) { throw 'Unexpected release URL.' }
    $client = [Net.Http.HttpClient]::new()
    $client.Timeout = [TimeSpan]::FromMinutes(60)
    $response = $null; $inputStream = $null; $outputStream = $null
    try {
        $response = $client.GetAsync(($manifest.download_base + $Name), [Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        $response.EnsureSuccessStatusCode() | Out-Null
        $inputStream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
        $outputStream = [IO.File]::Create($Destination)
        $inputStream.CopyToAsync($outputStream).GetAwaiter().GetResult()
    } finally {
        if ($outputStream) { $outputStream.Dispose() }; if ($inputStream) { $inputStream.Dispose() }
        if ($response) { $response.Dispose() }; $client.Dispose()
    }
}
Assert-PlainPath $runtimeRoot
if (Test-Path -LiteralPath $target) {
    Assert-PlainPath $target
    $receipt = Get-Content -LiteralPath (Join-Path $target 'install-receipt.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($receipt.runtime_id -ne $manifest.runtime_id -or $receipt.archive_sha256 -ne $manifest.archive_sha256 -or $receipt.msvc_sha256 -ne $manifest.msvc_sidecar.sha256) { throw 'Existing runtime receipt does not match; no files changed.' }
    Assert-Hash (Join-Path $target 'runtime-files.json') $manifest.runtime_files_sha256
    & (Join-Path $target 'python/python.exe') -X utf8 -I -B (Join-Path $PSScriptRoot 'narrate.py') --check
    if ($LASTEXITCODE -ne 0) { throw 'Existing runtime check failed. See installation manual for safe removal/reinstall.' }
    Write-Output "Runtime ready: $target"
    exit 0
}
if ($CheckOnly) { throw 'Runtime is not installed. Run install-runtime.ps1 without -CheckOnly.' }
$required = [double]$manifest.archive_bytes * 2 + [double]$manifest.unpacked_bytes + 1073741824
$drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($skillRoot))
if ($drive.AvailableFreeSpace -lt $required) { throw ('Insufficient free space; need about {0:N1} GiB during installation.' -f ($required/1GB)) }
Write-Output ("Install {0}; download {1:N2} GiB, unpack {2:N2} GiB; destination: {3}" -f $manifest.runtime_id, ($manifest.archive_bytes/1GB), ($manifest.unpacked_bytes/1GB), $target)
if ($DryRun) { exit 0 }
if ($BundleDirectory) { Assert-PlainPath $BundleDirectory }
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$stage = Join-Path $runtimeRoot ('.install-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
$cache = Join-Path $stage 'parts'
$payload = Join-Path $stage 'payload'
New-Item -ItemType Directory -Path $cache, $payload | Out-Null
$archive = Join-Path $stage 'runtime.zip'
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Add-Type -AssemblyName System.Net.Http
    foreach ($part in $manifest.parts) {
        if ($part.name -notmatch '^voice-runtime\.zip\.part[0-9]{3}$') { throw 'Unsafe part filename.' }
        $path = Join-Path $cache $part.name
        Write-Output "Preparing $($part.name)..."
        Receive-ReleaseFile $part.name $path
        if ((Get-Item -LiteralPath $path).Length -ne $part.bytes) { throw "Incomplete part: $($part.name)" }
        Assert-Hash $path $part.sha256
    }
    $joined = [IO.File]::Create($archive)
    try {
        foreach ($part in $manifest.parts) {
            $inputStream = [IO.File]::OpenRead((Join-Path $cache $part.name))
            try { $inputStream.CopyTo($joined) } finally { $inputStream.Dispose() }
        }
    } finally { $joined.Dispose() }
    Assert-Hash $archive $manifest.archive_sha256
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($archive)
    try {
        $prefix = [IO.Path]::GetFullPath($payload) + [IO.Path]::DirectorySeparatorChar
        foreach ($entry in $zip.Entries) {
            $destination = [IO.Path]::GetFullPath((Join-Path $payload $entry.FullName))
            if (-not $destination.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or $entry.FullName.Contains(':') -or $entry.FullName.Contains('\')) { throw 'Unsafe archive entry.' }
            if ($entry.FullName.EndsWith('/')) { [IO.Directory]::CreateDirectory($destination) | Out-Null; continue }
            [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($destination)) | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destination, $false)
        }
    } finally { $zip.Dispose() }
    Assert-Hash (Join-Path $payload 'runtime-files.json') $manifest.runtime_files_sha256
    $files = Get-Content -LiteralPath (Join-Path $payload 'runtime-files.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($files.runtime_id -ne $manifest.runtime_id) { throw 'Unexpected runtime file inventory.' }
    # The full archive SHA256 covers every extracted byte. Check that no file was skipped.
    foreach ($item in $files.files) {
        $destination = [IO.Path]::GetFullPath((Join-Path $payload $item.path))
        if (-not $destination.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe inventory path.' }
        if ((Get-Item -LiteralPath $destination).Length -ne $item.bytes) { throw "Extracted file size mismatch: $($item.path)" }
    }
    $sidecar = $manifest.msvc_sidecar
    if ($sidecar.name -ne 'msvc-applocal.zip') { throw 'Unexpected CRT sidecar name.' }
    $sidecarPath = Join-Path $stage $sidecar.name
    Receive-ReleaseFile $sidecar.name $sidecarPath
    if ((Get-Item -LiteralPath $sidecarPath).Length -ne $sidecar.bytes) { throw 'Incomplete CRT sidecar.' }
    Assert-Hash $sidecarPath $sidecar.sha256
    $crtZip = [IO.Compression.ZipFile]::OpenRead($sidecarPath)
    try {
        foreach ($entry in $crtZip.Entries) {
            if ($entry.FullName -notmatch '^(python/[a-zA-Z0-9_]+\.dll|licenses/Microsoft-CRT-NOTICE\.txt)$') { throw 'Unsafe CRT archive entry.' }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, (Join-Path $payload $entry.FullName), $true)
        }
    } finally { $crtZip.Dispose() }
    # Verify that dependencies resolve against the application-local CRT, not the source PC's DLLs.
    & (Join-Path $payload 'python/python.exe') -X utf8 -I -B -c 'import sys,torch,qwen_tts,numpy,soundfile,onnxruntime; assert sys.version_info[:2] == (3,12); print("Portable imports ready; CPU torch",torch.__version__)'
    if ($LASTEXITCODE -ne 0) { throw 'Portable Python import check failed; original environments were not modified.' }
    @{ runtime_id=$manifest.runtime_id; archive_sha256=$manifest.archive_sha256; msvc_sha256=$sidecar.sha256; installed_utc=[DateTime]::UtcNow.ToString('o'); owner='ai-daily-video/install-runtime.ps1' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $payload 'install-receipt.json') -Encoding UTF8
    # Commit only a new versioned directory; an existing runtime is never overwritten.
    [IO.Directory]::Move($payload, $target)
    Write-Output "Runtime installed: $target"
} catch {
    Write-Error ("Installation stopped; the staging directory is retained for inspection: {0}. {1}" -f $stage, $_.Exception.Message)
    exit 1
}
# Only remove the exact installer-owned staging directory after successful installation.
Assert-PlainPath $stage
if (-not ([IO.Path]::GetFullPath($stage)).StartsWith(([IO.Path]::GetFullPath($runtimeRoot) + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe cleanup path.' }
Remove-Item -LiteralPath $stage -Recurse -Force
