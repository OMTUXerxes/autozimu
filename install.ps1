param([switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$codexRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$skillsRoot = Join-Path $codexRoot 'skills'
$autoRoot = Join-Path $skillsRoot 'autozimu'
$jyRoot = Join-Path $skillsRoot 'jianying-editor'
$venvRoot = Join-Path $codexRoot 'autozimu-venv'
$jyCommit = '32c56928ded4f9e2c2b80e099dc7abb793d2c30b'

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
        [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
}

function Has-Python312 {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { return $false }
    try {
        & py -3.12 -c 'import sys; assert sys.version_info[:2] == (3, 12)' 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Has-Jianying {
    $draftDir = Join-Path $env:LOCALAPPDATA 'JianyingPro\User Data\Projects\com.lveditor.draft'
    if (Test-Path -LiteralPath $draftDir) { return $true }
    $uninstallKeys = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    return [bool](Get-ItemProperty $uninstallKeys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match '剪映专业版|JianyingPro' } | Select-Object -First 1)
}

function Install-Package([string]$id) {
    Write-Host "Installing $id..."
    & winget install --id $id --exact --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) { throw "winget failed: $id ($LASTEXITCODE)" }
    Refresh-Path
}

if ($CheckOnly) {
    [pscustomobject]@{
        Python312 = Has-Python312
        FFmpeg = [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue)
        FFprobe = [bool](Get-Command ffprobe -ErrorAction SilentlyContinue)
        Deno = [bool](Get-Command deno -ErrorAction SilentlyContinue)
        Jianying = Has-Jianying
        JianyingSkill = (Test-Path -LiteralPath (Join-Path $jyRoot 'scripts\jy_wrapper.py'))
        AutozimuSkill = (Test-Path -LiteralPath (Join-Path $autoRoot 'SKILL.md'))
        PythonEnv = (Test-Path -LiteralPath (Join-Path $venvRoot 'Scripts\python.exe'))
    } | Format-List
    exit 0
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw 'winget is missing. Install Microsoft App Installer, then rerun install.ps1.'
}
if (-not (Has-Python312)) { Install-Package 'Python.Python.3.12' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or
    -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) { Install-Package 'Gyan.FFmpeg' }
if (-not (Get-Command deno -ErrorAction SilentlyContinue)) { Install-Package 'DenoLand.Deno' }
if (-not (Has-Jianying)) { Install-Package 'ByteDance.JianyingPro' }

if (-not (Has-Python312)) { throw 'Python 3.12 is not visible yet. Open a new PowerShell and rerun this installer.' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or
    -not (Get-Command ffprobe -ErrorAction SilentlyContinue) -or
    -not (Get-Command deno -ErrorAction SilentlyContinue)) {
    throw 'FFmpeg/FFprobe/Deno is not visible yet. Open a new PowerShell and rerun this installer.'
}

New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null
if (-not (Test-Path -LiteralPath (Join-Path $jyRoot 'scripts\jy_wrapper.py'))) {
    if (Test-Path -LiteralPath $jyRoot) {
        throw "Incomplete jianying-editor skill at $jyRoot. Repair it before retrying."
    }
    $tempDir = Join-Path $env:TEMP ('autozimu-install-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    try {
        $archive = Join-Path $tempDir 'jianying-editor.zip'
        Invoke-WebRequest -Uri "https://github.com/luoluoluo22/jianying-editor-skill/archive/$jyCommit.zip" -OutFile $archive
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
        try {
            $names = @($zip.Entries | ForEach-Object FullName)
            if (-not ($names | Where-Object { $_ -match '/SKILL\.md$' }) -or
                -not ($names | Where-Object { $_ -match '/scripts/jy_wrapper\.py$' })) {
                throw 'Downloaded jianying-editor archive is incomplete.'
            }
        } finally { $zip.Dispose() }
        Expand-Archive -LiteralPath $archive -DestinationPath $tempDir
        $extracted = Get-ChildItem -LiteralPath $tempDir -Directory | Select-Object -First 1
        if (-not $extracted) { throw 'Downloaded jianying-editor archive has no source folder.' }
        Copy-Item -LiteralPath $extracted.FullName -Destination $jyRoot -Recurse
    } finally {
        $resolvedTemp = [System.IO.Path]::GetFullPath($tempDir)
        $resolvedBase = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
        if ($resolvedTemp.StartsWith($resolvedBase, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
        }
    }
}

New-Item -ItemType Directory -Force -Path $autoRoot | Out-Null
if ([System.IO.Path]::GetFullPath($source) -ne [System.IO.Path]::GetFullPath($autoRoot)) {
    foreach ($name in @('SKILL.md', 'AGENTS.md', 'README.md', 'LICENSE', 'install.ps1', 'scripts', 'assets')) {
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination $autoRoot -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $venvRoot 'Scripts\python.exe'))) {
    & py -3.12 -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment.' }
}
$python = Join-Path $venvRoot 'Scripts\python.exe'
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'Could not update pip.' }
& $python -m pip install 'yt-dlp[default]' Pillow faster-whisper
if ($LASTEXITCODE -ne 0) { throw 'Could not install autozimu Python packages.' }
& $python -m pip install -r (Join-Path $jyRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install jianying-editor Python packages.' }
& $python (Join-Path $autoRoot 'scripts\render.py') --check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
Write-Host "Installed autozimu and jianying-editor in $skillsRoot"
Write-Host 'Open Jianying once before your first project, so its draft folder is initialized.'
