# ============================================================================
# EPlusSimple runtime setup
# ============================================================================
#
# This script prepares a local runtime directory for EPlusSimple.
# It does not require system-wide Python or system-wide EnergyPlus.
#
# Final directory layout:
#
#   <repo root>/
#   |-- setup.bat
#   |-- requirements.txt
#   |-- src/
#   `-- runtime/
#      |-- python/                  Embedded Python runtime
#      |-- EnergyPlusV24-2-0/       Portable EnergyPlus 24.2 runtime
#      `-- downloads/               Temporary downloaded files, removed after success by default
#
# Design notes:
#
# 1. runtime/python is NOT a normal venv.
#    It is the official Windows embeddable Python distribution.
#
# 2. runtime/EnergyPlusV24-2-0 is NOT installed into Program Files.
#    It is extracted from the official EnergyPlus portable zip file.
#
# 3. This PowerShell script is used instead of putting all logic in setup.bat
#    because PowerShell is much safer for:
#      - downloading files,
#      - extracting zip archives,
#      - recursively locating energyplus.exe,
#      - copying directory contents without robocopy parsing issues.
#
# 4. This file intentionally uses ASCII comments. This avoids code-page issues
#    when the file is opened or executed on different Windows environments.
#
# Recommended .gitignore entries:
#
#   /runtime/
#   /venv/
#
# ============================================================================

[CmdletBinding()]
param(
    # Force reinstallation of both Python and EnergyPlus runtime directories.
    [switch]$Force,

    # Skip Python package installation from requirements.txt.
    [switch]$SkipRequirements,

    # Keep the temporary EnergyPlus extraction directory for debugging.
    [switch]$KeepExtractedEnergyPlus,

    # Keep downloaded zip/bootstrap files after a successful setup.
    # By default, runtime/downloads is removed after all setup steps complete
    # to avoid leaving large files such as the EnergyPlus portable zip.
    [switch]$KeepDownloads
)

Set-StrictMode -Version 1.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ============================================================================
# [0] Common paths
# ============================================================================
# setup.ps1 is expected to be located at:
#   <repo root>/scripts/dev/setup.ps1
# Therefore, the repository root is two levels above $PSScriptRoot.
# ============================================================================

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$RuntimeDir = Join-Path $RepoRoot 'runtime'
$DownloadDir = Join-Path $RuntimeDir 'downloads'

# ============================================================================
# [1] Python runtime configuration
# ============================================================================

$PythonVersionShort = '312'
$PythonVersionFull = '3.12.7'
$PythonDir = Join-Path $RuntimeDir 'PythonV3-12-7'
$PythonExe = Join-Path $PythonDir 'python.exe'
$PipExe = Join-Path $PythonDir 'Scripts\pip.exe'
$PythonZipFileName = "python-$PythonVersionFull-embed-amd64.zip"
$PythonZipPath = Join-Path $DownloadDir $PythonZipFileName
$PythonDownloadUrl = "https://www.python.org/ftp/python/$PythonVersionFull/$PythonZipFileName"
$PythonPthFile = Join-Path $PythonDir "python$PythonVersionShort._pth"

# This path is written into python312._pth.
# It is relative to runtime/python/python.exe.
$SrcPathForPth = '..\..\src'

$GetPipUrl = 'https://bootstrap.pypa.io/get-pip.py'
$GetPipPath = Join-Path $DownloadDir 'get-pip.py'

# ============================================================================
# [2] EnergyPlus portable runtime configuration
# ============================================================================
# v24.2.0a is the bug-fix release for EnergyPlus 24.2.0.
# The official zip expands into a folder named roughly like:
#   EnergyPlus-24.2.0-94a887817b-Windows-x86_64
# This script extracts it to a temporary folder, finds the real folder that
# contains energyplus.exe, and copies that folder's CONTENTS into:
#   runtime/EnergyPlusV24-2-0
# ============================================================================

$EnergyPlusVersion = '24.2.0'
$EnergyPlusBuild = '94a887817b'
$EnergyPlusTag = 'v24.2.0a'
$EnergyPlusPlatform = 'Windows-x86_64'
$EnergyPlusFolderName = 'EnergyPlusV24-2-0'
$EnergyPlusDir = Join-Path $RuntimeDir $EnergyPlusFolderName
$EnergyPlusExe = Join-Path $EnergyPlusDir 'energyplus.exe'
$EnergyPlusZipFileName = "EnergyPlus-$EnergyPlusVersion-$EnergyPlusBuild-$EnergyPlusPlatform.zip"
$EnergyPlusZipPath = Join-Path $DownloadDir $EnergyPlusZipFileName
$EnergyPlusDownloadUrl = "https://github.com/NREL/EnergyPlus/releases/download/$EnergyPlusTag/$EnergyPlusZipFileName"
$EnergyPlusExtractDir = Join-Path $RuntimeDir '_energyplus_extract'
$EnergyPlusLegacyDir = Join-Path $RuntimeDir 'energyplus'

# ============================================================================
# Helper functions
# ============================================================================

function Write-Step {
    param([string]$Message)
    Write-Host $Message
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

function Remove-DirectoryIfExists {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Download-FileIfMissing {
    param(
        [string]$Url,
        [string]$Destination
    )

    if (Test-Path -LiteralPath $Destination) {
        Write-Host "    ...Using cached file: $Destination"
        return
    }

    Write-Host "    ...Downloading: $Url"
    Write-Host "       Target    : $Destination"

    try {
        Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
    }
    catch {
        throw "Download failed. URL: $Url. Error: $($_.Exception.Message)"
    }

    if (-not (Test-Path -LiteralPath $Destination)) {
        throw "Downloaded file was not created: $Destination"
    }
}

function Expand-ZipClean {
    param(
        [string]$ZipPath,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $ZipPath)) {
        throw "Zip file does not exist: $ZipPath"
    }

    Remove-DirectoryIfExists $Destination
    Ensure-Directory $Destination

    Write-Host "    ...Extracting zip: $ZipPath"
    Write-Host "       To        : $Destination"

    try {
        Expand-Archive -LiteralPath $ZipPath -DestinationPath $Destination -Force
    }
    catch {
        throw "Zip extraction failed. Zip: $ZipPath. Error: $($_.Exception.Message)"
    }
}

function Add-UniqueLine {
    param(
        [string]$Path,
        [string]$Line
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Target file does not exist: $Path"
    }

    $lines = Get-Content -LiteralPath $Path -ErrorAction Stop
    if ($lines -contains $Line) {
        Write-Host "    ...Already in ._pth: $Line"
    }
    else {
        Add-Content -LiteralPath $Path -Value $Line
        Write-Host "    ...Added to ._pth: $Line"
    }
}

function Invoke-ExternalCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments = @()
    )

    Write-Host "    ...Running: $FilePath $($Arguments -join ' ')"
    & $FilePath @Arguments
    $exitCode = $LASTEXITCODE
    if ($null -ne $exitCode -and $exitCode -ne 0) {
        throw "Command failed with exit code $exitCode`: $FilePath $($Arguments -join ' ')"
    }
}

# ============================================================================
# Setup steps
# ============================================================================

function Setup-PythonRuntime {
    Write-Step '[1/4] Checking Python runtime...'

    if ($Force -and (Test-Path -LiteralPath $PythonDir)) {
        Write-Host "    ...Force enabled. Removing existing Python runtime: $PythonDir"
        Remove-DirectoryIfExists $PythonDir
    }

    if (Test-Path -LiteralPath $PythonExe) {
        Write-Host "    ...Found Python runtime: $PythonExe"
        return
    }

    Download-FileIfMissing -Url $PythonDownloadUrl -Destination $PythonZipPath

    Remove-DirectoryIfExists $PythonDir
    Ensure-Directory $PythonDir

    Write-Host "    ...Extracting Python package."
    Expand-Archive -LiteralPath $PythonZipPath -DestinationPath $PythonDir -Force

    if (-not (Test-Path -LiteralPath $PythonExe)) {
        throw "python.exe was not found after extraction. Expected: $PythonExe"
    }
}

function Configure-PythonPaths {
    Write-Step '[2/4] Configuring Python runtime paths...'

    if (-not (Test-Path -LiteralPath $PythonPthFile)) {
        throw "Python ._pth file was not found: $PythonPthFile"
    }

    Add-UniqueLine -Path $PythonPthFile -Line 'Lib\site-packages'
    Add-UniqueLine -Path $PythonPthFile -Line $SrcPathForPth
    Add-UniqueLine -Path $PythonPthFile -Line 'import site'

    Write-Host "    ...Configured: $PythonPthFile"
}

function Setup-PipAndPackages {
    Write-Step '[3/4] Installing pip and Python packages...'

    if (-not (Test-Path -LiteralPath $PipExe)) {
        Download-FileIfMissing -Url $GetPipUrl -Destination $GetPipPath
        Invoke-ExternalCommand -FilePath $PythonExe -Arguments @($GetPipPath)
    }
    else {
        Write-Host "    ...Found pip: $PipExe"
    }

    Invoke-ExternalCommand -FilePath $PipExe -Arguments @('install', '--upgrade', 'setuptools', 'wheel')

    $RequirementsPath = Join-Path $RepoRoot 'requirements.txt'
    if ($SkipRequirements) {
        Write-Host '    ...SkipRequirements enabled. Skipping requirements.txt installation.'
    }
    elseif (Test-Path -LiteralPath $RequirementsPath) {
        Invoke-ExternalCommand -FilePath $PipExe -Arguments @('install', '-r', $RequirementsPath)
    }
    else {
        Write-Warning "requirements.txt was not found. Skipping package installation: $RequirementsPath"
    }
}

function Setup-EnergyPlusRuntime {
    Write-Step '[4/4] Checking EnergyPlus runtime...'

    if ($Force -and (Test-Path -LiteralPath $EnergyPlusDir)) {
        Write-Host "    ...Force enabled. Removing existing EnergyPlus runtime: $EnergyPlusDir"
        Remove-DirectoryIfExists $EnergyPlusDir
    }

    if (Test-Path -LiteralPath $EnergyPlusExe) {
        Write-Host "    ...Found EnergyPlus runtime: $EnergyPlusExe"
        & $EnergyPlusExe --version
        return
    }

    # Remove the older unversioned layout produced by an earlier setup draft.
    if (Test-Path -LiteralPath $EnergyPlusLegacyDir) {
        Write-Host "    ...Removing legacy EnergyPlus folder: $EnergyPlusLegacyDir"
        Remove-DirectoryIfExists $EnergyPlusLegacyDir
    }

    Download-FileIfMissing -Url $EnergyPlusDownloadUrl -Destination $EnergyPlusZipPath
    Expand-ZipClean -ZipPath $EnergyPlusZipPath -Destination $EnergyPlusExtractDir

    # Locate the real EnergyPlus executable inside the extracted zip.
    #
    # Do NOT use .Count here. On some Windows PowerShell configurations,
    # a single result may be treated as a scalar object, and StrictMode can
    # report: "The property 'Count' cannot be found on this object."
    #
    # Also avoid the -File switch for broader compatibility. Instead, filter
    # with PSIsContainer so this works in older Windows PowerShell versions too.
    $candidate = Get-ChildItem -LiteralPath $EnergyPlusExtractDir -Recurse -ErrorAction Stop |
        Where-Object { (-not $_.PSIsContainer) -and ($_.Name -ieq 'energyplus.exe') } |
        Select-Object -First 1

    if ($null -eq $candidate) {
        throw "energyplus.exe was not found inside the extracted package: $EnergyPlusExtractDir"
    }

    $sourceDir = $candidate.Directory.FullName
    Write-Host '    ...Found EnergyPlus source directory:'
    Write-Host "       $sourceDir"

    Remove-DirectoryIfExists $EnergyPlusDir
    Ensure-Directory $EnergyPlusDir

    Write-Host '    ...Copying EnergyPlus files to:'
    Write-Host "       $EnergyPlusDir"

    # Copy the contents of the source folder, not the wrapper folder itself.
    # This produces:
    #   runtime/EnergyPlusV24-2-0/energyplus.exe
    # rather than:
    #   runtime/EnergyPlusV24-2-0/EnergyPlus-24.2.0-.../energyplus.exe
    Get-ChildItem -LiteralPath $sourceDir -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $EnergyPlusDir -Recurse -Force
    }

    if (-not $KeepExtractedEnergyPlus) {
        Remove-DirectoryIfExists $EnergyPlusExtractDir
    }
    else {
        Write-Host "    ...Keeping extracted EnergyPlus directory for debugging: $EnergyPlusExtractDir"
    }

    if (-not (Test-Path -LiteralPath $EnergyPlusExe)) {
        throw "EnergyPlus executable was not found after setup. Expected: $EnergyPlusExe"
    }

    Write-Host '    ...EnergyPlus setup complete.'
    & $EnergyPlusExe --version
}


function Cleanup-DownloadsAfterSuccess {
    Write-Step '[cleanup] Checking downloaded setup files...'

    if ($KeepDownloads) {
        Write-Host "    ...KeepDownloads enabled. Keeping: $DownloadDir"
        return
    }

    if (Test-Path -LiteralPath $DownloadDir) {
        Write-Host "    ...Removing downloaded setup files: $DownloadDir"
        Remove-DirectoryIfExists $DownloadDir
    }
    else {
        Write-Host '    ...No downloads directory to remove.'
    }
}

# ============================================================================
# Main
# ============================================================================

try {
    Write-Host ''
    Write-Host '============================================================================'
    Write-Host ' EPlusSimple runtime setup'
    Write-Host '============================================================================'
    Write-Host ''
    Write-Host "Repository : $RepoRoot"
    Write-Host "Runtime    : $RuntimeDir"
    Write-Host ''

    Ensure-Directory $RuntimeDir
    Ensure-Directory $DownloadDir

    Setup-PythonRuntime
    Configure-PythonPaths
    Setup-PipAndPackages
    Setup-EnergyPlusRuntime
    Cleanup-DownloadsAfterSuccess

    Write-Host ''
    Write-Host '============================================================================'
    Write-Host ' Runtime setup is complete.'
    Write-Host '============================================================================'
    Write-Host ''
    Write-Host "Python     : $PythonExe"
    Write-Host "EnergyPlus : $EnergyPlusExe"
    Write-Host "Runtime    : $RuntimeDir"
    Write-Host ''
    exit 0
}
catch {
    Write-Host ''
    Write-Host '============================================================================' -ForegroundColor Red
    Write-Host ' [ERROR] Runtime setup failed.' -ForegroundColor Red
    Write-Host '============================================================================' -ForegroundColor Red
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ''
    Write-Host 'Suggested checks:'
    Write-Host '  1. Delete runtime/downloads if a cached zip file is corrupted.'
    Write-Host '  2. Delete runtime/_energyplus_extract if a previous extraction was interrupted.'
    Write-Host '  3. Re-run setup.bat from the repository root.'
    Write-Host ''
    Write-Host 'Note:'
    Write-Host '  runtime/downloads is intentionally kept when setup fails so that you can'
    Write-Host '  inspect or reuse the downloaded files during troubleshooting.'
    Write-Host ''
    exit 1
}
