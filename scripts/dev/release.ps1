# ============================================================================
# EPlusSimple release script
# Release script revision: standard-single-target-approved-verbs-20260612
# ============================================================================
#
# Expected location:
#   scripts\release.ps1
# or:
#   scripts\dev\release.ps1
#
# Intended caller:
#   runscript.bat release ...
#
# This script creates:
#   dist\EPlusSimple_V<Version>\
#   dist\EPlusSimple_V<Version>.zip
#
# Notes:
# - There is no target option.
# - The standard package is the only release package.
# - Detailed release log is written to logs\release.log.
# ============================================================================

[CmdletBinding()]
param(
    # Release version without leading V.
    [string]$Version = '0.6.2',

    # Skip regression only when iterating on packaging logic.
    [switch]$SkipRegressionTest,

    # Skip documentation build when latexmk is not available or when testing
    # packaging-only changes.
    [switch]$SkipDocs,

    # Keep the existing dist directory.
    # Useful for debugging, but not recommended for normal releases.
    [switch]$NoClean
)

Set-StrictMode -Version 1.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ----------------------------------------------------------------------------
# Repository root
# ----------------------------------------------------------------------------

function Resolve-RepoRoot {
    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName

    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
        $scriptDir = Split-Path -Parent $PSCommandPath
    }

    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
        throw 'Cannot resolve script directory. Run this script from a saved .ps1 file.'
    }

    $candidates = @(
        $scriptDir,
        (Join-Path $scriptDir '..'),
        (Join-Path $scriptDir '..\..')
    )

    foreach ($candidate in $candidates) {
        $resolved = $null

        try {
            $resolved = (Resolve-Path -LiteralPath $candidate -ErrorAction Stop).Path
        } catch {
            continue
        }

        if (
            (Test-Path -LiteralPath (Join-Path $resolved 'src') -PathType Container) -and
            (Test-Path -LiteralPath (Join-Path $resolved 'runtime') -PathType Container) -and
            (Test-Path -LiteralPath (Join-Path $resolved 'scripts') -PathType Container)
        ) {
            return $resolved
        }
    }

    throw "Cannot resolve repository root from script directory: $scriptDir"
}

$RepoRoot = Resolve-RepoRoot
Set-Location $RepoRoot

# ----------------------------------------------------------------------------
# Path configuration
# ----------------------------------------------------------------------------

$ProjectName = 'EPlusSimple'
$VersionString = "V$Version"
$ReleaseName = "$ProjectName`_$VersionString"

$DistDir = Join-Path $RepoRoot 'dist'
$ReleaseDir = Join-Path $DistDir $ReleaseName
$OutputZip = Join-Path $DistDir "$ReleaseName.zip"

$LogsDir = Join-Path $RepoRoot 'logs'
$ReleaseLog = Join-Path $LogsDir 'release.log'
$TempLogDir = Join-Path $LogsDir '_tmp_release'

$RuntimeDir = Join-Path $RepoRoot 'runtime'

$PythonRuntimeName = 'PythonV3-12-7'
$EnergyPlusRuntimeName = 'EnergyPlusV24-2-0'
$WeatherRuntimeName = 'Weather'

$PythonDir = Join-Path $RuntimeDir $PythonRuntimeName
$PythonExe = Join-Path $PythonDir 'python.exe'
$PythonPthFileName = 'python312._pth'
$PythonPthFile = Join-Path $PythonDir $PythonPthFileName

$EnergyPlusDir = Join-Path $RuntimeDir $EnergyPlusRuntimeName
$EnergyPlusExe = Join-Path $EnergyPlusDir 'energyplus.exe'

$WeatherRootDir = Join-Path $RuntimeDir $WeatherRuntimeName
$WeatherTmyDir = Join-Path $WeatherRootDir 'TMY'

$BuildGoScript = Join-Path $RepoRoot 'scripts\dev\build-go.ps1'
$EPlusSimpleCLIExe = Join-Path $RepoRoot 'EPlusSimpleCLI.exe'
$EPlusSimpleLauncherExe = Join-Path $RepoRoot 'EPlusSimpleLauncher.exe'

$ExamplesDir = Join-Path $RepoRoot 'examples'
$DocsDir = Join-Path $RepoRoot 'docs'
$SrcDir = Join-Path $RepoRoot 'src'

$RegressionTestScript = Join-Path $RepoRoot 'scripts\dev\regressiontest.py'
$RegressionLogLegacy = Join-Path $RepoRoot 'regtest.log'

$EnergyPlusPruneDirs = @(
    'DataSets',
    'Documentation',
    'ExampleFiles',
    'WeatherData',
    'MacroDataSets'
)

$script:CurrentStep = 'initializing release script'
$script:LogStream = $null
$script:LogWriter = $null

# ----------------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------------

function New-DirectoryIfMissing {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Open-ReleaseLog {
    New-DirectoryIfMissing $LogsDir

    if ($null -ne $script:LogWriter) {
        Close-ReleaseLog
    }

    $script:LogStream = [System.IO.FileStream]::new(
        $ReleaseLog,
        [System.IO.FileMode]::Create,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::ReadWrite
    )

    $encoding = [System.Text.UTF8Encoding]::new($false)
    $script:LogWriter = [System.IO.StreamWriter]::new($script:LogStream, $encoding)
    $script:LogWriter.AutoFlush = $true

    Write-LogRaw '============================================================================'
    Write-LogRaw ' EPlusSimple release log'
    Write-LogRaw '============================================================================'
    Write-LogRaw "Started      : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-LogRaw "Repository   : $RepoRoot"
    Write-LogRaw "Version      : $VersionString"
    Write-LogRaw "Release dir  : $ReleaseDir"
    Write-LogRaw "Release zip  : $OutputZip"
    Write-LogRaw '============================================================================'
    Write-LogRaw ''
}

function Close-ReleaseLog {
    if ($null -ne $script:LogWriter) {
        try {
            $script:LogWriter.Flush()
            $script:LogWriter.Close()
        } catch {
            # Avoid masking the original release error.
        }

        $script:LogWriter = $null
    }

    if ($null -ne $script:LogStream) {
        try {
            $script:LogStream.Close()
        } catch {
            # Avoid masking the original release error.
        }

        $script:LogStream = $null
    }
}

function Write-LogRaw {
    param([string]$Message)

    if ($null -eq $script:LogWriter) {
        return
    }

    $script:LogWriter.WriteLine($Message)
}

function Write-Log {
    param([string]$Message)

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Write-LogRaw "[$timestamp] $Message"
}

function Write-LogBlock {
    param(
        [string]$Title,
        [string[]]$Lines = @()
    )

    Write-LogRaw ''
    Write-LogRaw "===== $Title ====="

    foreach ($line in @($Lines)) {
        if ($null -eq $line) {
            Write-LogRaw ''
        } else {
            Write-LogRaw ([string]$line)
        }
    }
}

function Write-Step {
    param([string]$Message)

    $script:CurrentStep = $Message
    Write-Host $Message
    Write-Log $Message
}

function Write-ProgressLine {
    param([string]$Message)

    Write-Host " ...$Message"
    Write-Log " ...$Message"
}

# ----------------------------------------------------------------------------
# Generic helpers
# ----------------------------------------------------------------------------

function Remove-DirectoryIfExists {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path -PathType Container) {
        Write-Log "Removing directory: $Path"
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Remove-FileIfExists {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Write-Log "Removing file: $Path"
        Remove-Item -LiteralPath $Path -Force
    }
}

function Test-FileExists {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Message`nMissing file: $Path"
    }

    Write-Log "Validated file: $Path"
}

function Test-DirectoryExists {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Message`nMissing directory: $Path"
    }

    Write-Log "Validated directory: $Path"
}

function Invoke-LoggedCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $RepoRoot,
        [string]$Description = 'external command'
    )

    Write-ProgressLine $Description

    $commandLine = "$FilePath " + (($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_.Replace('"', '\"')) + '"'
        } else {
            $_
        }
    }) -join ' ')

    Write-LogBlock -Title "COMMAND: $Description" -Lines @(
        "Working directory: $WorkingDirectory",
        "Command          : $commandLine"
    )

    Push-Location $WorkingDirectory

    try {
        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE

        foreach ($line in @($output)) {
            Write-Log ([string]$line)
        }

        if ($null -eq $exitCode) {
            $exitCode = 0
        }

        Write-Log "Exit code: $exitCode"

        if ($exitCode -ne 0) {
            throw "$Description failed. Exit code: $exitCode. See log: $ReleaseLog"
        }
    } finally {
        Pop-Location
    }
}

function Copy-Directory {
    param(
        [string]$Source,
        [string]$Destination
    )

    Test-DirectoryExists -Path $Source -Message 'Cannot copy directory because the source directory was not found.'
    Remove-DirectoryIfExists $Destination

    $parent = Split-Path -Parent $Destination
    New-DirectoryIfMissing $parent

    Write-Log "Copy directory: $Source -> $Destination"
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Copy-File {
    param(
        [string]$Source,
        [string]$Destination
    )

    Test-FileExists -Path $Source -Message 'Cannot copy file because the source file was not found.'

    $parent = Split-Path -Parent $Destination
    New-DirectoryIfMissing $parent

    Write-Log "Copy file: $Source -> $Destination"
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Add-UniqueLine {
    param(
        [string]$Path,
        [string]$Line
    )

    Test-FileExists -Path $Path -Message 'Cannot update file because it was not found.'

    $lines = Get-Content -LiteralPath $Path -ErrorAction Stop

    if ($lines -contains $Line) {
        Write-Log "Already present in file: $Path :: $Line"
    } else {
        [System.IO.File]::AppendAllText(
            $Path,
            "`r`n$Line",
            [System.Text.UTF8Encoding]::new($false)
        )
        Write-Log "Added to file: $Path :: $Line"
    }
}

# ----------------------------------------------------------------------------
# Release steps
# ----------------------------------------------------------------------------

function Test-ReleaseInputs {
    Write-Step '[0/7] Validating release inputs...'

    Test-DirectoryExists -Path $SrcDir -Message 'src directory was not found.'
    Test-DirectoryExists -Path $ExamplesDir -Message 'examples directory was not found.'
    Test-DirectoryExists -Path $DocsDir -Message 'docs directory was not found.'

    Test-DirectoryExists -Path (Join-Path $SrcDir 'epsimple') -Message 'src\epsimple was not found.'
    Test-DirectoryExists -Path (Join-Path $SrcDir 'idragon') -Message 'src\idragon was not found.'
    Test-DirectoryExists -Path (Join-Path $SrcDir 'launcher') -Message 'src\launcher was not found.'

    Test-FileExists -Path (Join-Path $SrcDir 'launcher\core.py') -Message 'launcher core.py was not found.'
    Test-DirectoryExists -Path (Join-Path $SrcDir 'launcher\templates') -Message 'launcher templates directory was not found.'
    Test-DirectoryExists -Path (Join-Path $SrcDir 'launcher\static') -Message 'launcher static directory was not found.'

    Test-FileExists -Path $PythonExe -Message 'Python runtime was not found. Run "runscript setup" before release.'
    Test-FileExists -Path $PythonPthFile -Message 'Python ._pth file was not found. Run "runscript setup" before release.'
    Test-FileExists -Path $EnergyPlusExe -Message 'EnergyPlus runtime was not found. Run "runscript setup" before release.'
    Test-DirectoryExists -Path $WeatherTmyDir -Message 'Korean TMY weather data was not found. Run "runscript setup" before release.'

    Test-FileExists -Path $BuildGoScript -Message 'Go build script was not found.'
    Test-DirectoryExists -Path (Join-Path $RepoRoot 'tools\go') -Message 'Go source directory was not found.'
    Test-FileExists -Path (Join-Path $RepoRoot 'tools\go\go.mod') -Message 'Go module file was not found.'

    if (-not $SkipRegressionTest) {
        Test-FileExists -Path $RegressionTestScript -Message 'Regression test script was not found.'
    }

    Write-LogBlock -Title 'RELEASE INPUTS' -Lines @(
        "Repository   : $RepoRoot",
        "Version      : $VersionString",
        "Python       : $PythonExe",
        "EnergyPlus   : $EnergyPlusExe",
        "Weather TMY  : $WeatherTmyDir",
        "Go build     : $BuildGoScript",
        "Skip docs    : $SkipDocs",
        "Skip regtest : $SkipRegressionTest",
        "No clean     : $NoClean"
    )
}

function Initialize-Dist {
    Write-Step '[1/7] Preparing dist directory...'

    if (-not $NoClean) {
        Remove-DirectoryIfExists $DistDir
    }

    New-DirectoryIfMissing $ReleaseDir
    Write-Log "Release directory prepared: $ReleaseDir"
}

function Invoke-GoLauncherBuild {
    Write-Log 'Building Go executables.'

    Invoke-LoggedCommand `
        -FilePath 'powershell.exe' `
        -Arguments @(
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            $BuildGoScript,
            '-RepoRoot',
            $RepoRoot
        ) `
        -WorkingDirectory $RepoRoot `
        -Description 'Go executable build'

    Test-FileExists -Path $EPlusSimpleCLIExe -Message 'EPlusSimpleCLI.exe was not generated by build-go.ps1.'
    Test-FileExists -Path $EPlusSimpleLauncherExe -Message 'EPlusSimpleLauncher.exe was not generated by build-go.ps1.'

    Write-Log 'Go executables built.'
}

function Remove-EnergyPlusReleaseExtras {
    param([string]$ReleaseEnergyPlusDir)

    Test-DirectoryExists -Path $ReleaseEnergyPlusDir -Message 'Release EnergyPlus runtime was not found.'

    foreach ($dirname in $EnergyPlusPruneDirs) {
        $target = Join-Path $ReleaseEnergyPlusDir $dirname

        if (Test-Path -LiteralPath $target -PathType Container) {
            Remove-DirectoryIfExists $target
            Write-Log "Pruned EnergyPlus folder: $dirname"
        } else {
            Write-Log "EnergyPlus folder not found, skipped: $dirname"
        }
    }
}

function Copy-RuntimeAndRootFiles {
    Write-Step '[2/7] Copying runtime and root files...'

    $ReleaseRuntimeDir = Join-Path $ReleaseDir 'runtime'
    New-DirectoryIfMissing $ReleaseRuntimeDir

    Copy-Directory -Source $PythonDir -Destination (Join-Path $ReleaseRuntimeDir $PythonRuntimeName)

    $ReleaseEnergyPlusDir = Join-Path $ReleaseRuntimeDir $EnergyPlusRuntimeName
    Copy-Directory -Source $EnergyPlusDir -Destination $ReleaseEnergyPlusDir
    Remove-EnergyPlusReleaseExtras -ReleaseEnergyPlusDir $ReleaseEnergyPlusDir

    $ReleaseWeatherRootDir = Join-Path $ReleaseRuntimeDir $WeatherRuntimeName
    New-DirectoryIfMissing $ReleaseWeatherRootDir
    Copy-Directory -Source $WeatherTmyDir -Destination (Join-Path $ReleaseWeatherRootDir 'TMY')

    Copy-Directory -Source $ExamplesDir -Destination (Join-Path $ReleaseDir 'examples')

    Invoke-GoLauncherBuild

    Copy-File -Source $EPlusSimpleCLIExe -Destination (Join-Path $ReleaseDir 'EPlusSimpleCLI.exe')
    Copy-File -Source $EPlusSimpleLauncherExe -Destination (Join-Path $ReleaseDir 'EPlusSimpleLauncher.exe')

    Write-Log 'Runtime, weather data, examples, and root executables copied.'
}

function Set-ReleaseRuntime {
    Write-Step '[3/7] Configuring release runtime paths...'

    $ReleasePthFile = Join-Path $ReleaseDir "runtime\$PythonRuntimeName\$PythonPthFileName"

    Add-UniqueLine -Path $ReleasePthFile -Line 'Lib\site-packages'
    Add-UniqueLine -Path $ReleasePthFile -Line '..\..\src'
    Add-UniqueLine -Path $ReleasePthFile -Line 'import site'

    Write-Log 'Release runtime paths configured.'
}

function Set-ReleaseEnvironment {
    $env:EPSIMPLE_RUNTIME_DIR = $RuntimeDir
    $env:IDRAGON_RUNTIME_DIR = $RuntimeDir
    $env:IDRAGON_ENERGYPLUS_DIR = $EnergyPlusDir
    $env:ENERGYPLUS_DIR = $EnergyPlusDir
    $env:ENERGYPLUS_EXE = $EnergyPlusExe
    $env:EPSIMPLE_WEATHER_DIR = $WeatherRootDir
    $env:EPSIMPLE_TMY_DIR = $WeatherTmyDir
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PATH = "$EnergyPlusDir;$env:PATH"

    Write-LogBlock -Title 'RELEASE ENVIRONMENT' -Lines @(
        "EPSIMPLE_RUNTIME_DIR    = $env:EPSIMPLE_RUNTIME_DIR",
        "IDRAGON_RUNTIME_DIR     = $env:IDRAGON_RUNTIME_DIR",
        "IDRAGON_ENERGYPLUS_DIR  = $env:IDRAGON_ENERGYPLUS_DIR",
        "ENERGYPLUS_DIR          = $env:ENERGYPLUS_DIR",
        "ENERGYPLUS_EXE          = $env:ENERGYPLUS_EXE",
        "EPSIMPLE_WEATHER_DIR    = $env:EPSIMPLE_WEATHER_DIR",
        "EPSIMPLE_TMY_DIR        = $env:EPSIMPLE_TMY_DIR",
        "PYTHONNOUSERSITE        = $env:PYTHONNOUSERSITE",
        "PATH head               = $($env:PATH.Split(';')[0])"
    )
}

function Invoke-RegressionTest {
    if ($SkipRegressionTest) {
        Write-Step '[4/7] Skipping regression test.'
        return
    }

    Write-Step '[4/7] Running regression test...'

    Set-ReleaseEnvironment
    Remove-FileIfExists $RegressionLogLegacy

    Invoke-LoggedCommand `
        -FilePath $PythonExe `
        -Arguments @('--version') `
        -WorkingDirectory $RepoRoot `
        -Description 'Python version check'

    Invoke-LoggedCommand `
        -FilePath $EnergyPlusExe `
        -Arguments @('--version') `
        -WorkingDirectory $RepoRoot `
        -Description 'EnergyPlus version check'

    Invoke-LoggedCommand `
        -FilePath $PythonExe `
        -Arguments @($RegressionTestScript) `
        -WorkingDirectory $RepoRoot `
        -Description 'Regression test'

    if (Test-Path -LiteralPath $RegressionLogLegacy -PathType Leaf) {
        $regLines = Get-Content -LiteralPath $RegressionLogLegacy -ErrorAction SilentlyContinue
        Write-LogBlock -Title 'REGRESSION TEST LOG FILE: regtest.log' -Lines @($regLines)
        Remove-FileIfExists $RegressionLogLegacy
    }

    Write-Log 'Regression test passed.'
}

function Write-ReleaseInfo {
    $today = Get-Date -Format 'yyyy.MM.dd.'
    $releaseInfoPath = Join-Path $DocsDir 'releaseinfo.tex'

    @"
\newcommand{\releaseversion}{$VersionString}
\newcommand{\releasedate}{$today}
"@ | Set-Content -LiteralPath $releaseInfoPath -Encoding UTF8

    Write-Log "Updated release info: $releaseInfoPath"
}

function Invoke-DocBuild {
    param(
        [string]$SourceName,
        [string]$DisplayName
    )

    $DocsBuildDir = Join-Path $DistDir 'docs'
    $ReleaseDocsDir = Join-Path $ReleaseDir 'docs'

    New-DirectoryIfMissing $DocsBuildDir
    New-DirectoryIfMissing $ReleaseDocsDir

    $texFile = "$SourceName.tex"
    $pdfFile = Join-Path $DocsBuildDir "$SourceName.pdf"
    $releasePdfFile = Join-Path $ReleaseDocsDir "$DisplayName.pdf"

    Invoke-LoggedCommand `
        -FilePath 'latexmk' `
        -Arguments @(
            '-silent',
            '-pdf',
            '-outdir=../dist/docs',
            $texFile
        ) `
        -WorkingDirectory $DocsDir `
        -Description "LaTeX build: $DisplayName"

    Test-FileExists -Path $pdfFile -Message "Expected PDF was not generated for $DisplayName."
    Copy-File -Source $pdfFile -Destination $releasePdfFile
}

function Invoke-DocumentationBuild {
    if ($SkipDocs) {
        Write-Step '[5/7] Skipping documentation build.'
        return
    }

    Write-Step '[5/7] Building documentation...'

    Write-ReleaseInfo

    Invoke-DocBuild -SourceName 'mainTRM' -DisplayName 'Technical Reference Manual'
    Invoke-DocBuild -SourceName 'mainRTR' -DisplayName 'Regression Test Report'
    Invoke-DocBuild -SourceName 'mainRN' -DisplayName 'Release Note'

    Write-Log 'Documentation build completed.'
}

function Copy-SourceFiles {
    Write-Step '[6/7] Copying source files...'

    $ReleaseSrcDir = Join-Path $ReleaseDir 'src'
    New-DirectoryIfMissing $ReleaseSrcDir

    Copy-Directory -Source (Join-Path $SrcDir 'epsimple') -Destination (Join-Path $ReleaseSrcDir 'epsimple')
    Copy-Directory -Source (Join-Path $SrcDir 'idragon') -Destination (Join-Path $ReleaseSrcDir 'idragon')

    Write-Log 'Source files copied.'
}

function New-ReleaseArchive {
    Write-Step '[7/7] Creating release zip...'

    Remove-FileIfExists $OutputZip

    Invoke-LoggedCommand `
        -FilePath 'tar' `
        -Arguments @(
            '-a',
            '-c',
            '-f',
            $OutputZip,
            '.'
        ) `
        -WorkingDirectory $ReleaseDir `
        -Description 'Archive creation'

    Test-FileExists -Path $OutputZip -Message 'Release zip was not created.'
    Write-Log "Archive created: $OutputZip"
}

function Write-FailureReport {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)

    Write-LogBlock -Title 'RELEASE FAILED' -Lines @(
        "Current step   : $script:CurrentStep",
        "Exception type : $($ErrorRecord.Exception.GetType().FullName)",
        "Message        : $($ErrorRecord.Exception.Message)"
    )

    if ($null -ne $ErrorRecord.InvocationInfo) {
        Write-LogBlock -Title 'FAILURE LOCATION' -Lines @(
            "Script : $($ErrorRecord.InvocationInfo.ScriptName)",
            "Line   : $($ErrorRecord.InvocationInfo.ScriptLineNumber)",
            "Command: $($ErrorRecord.InvocationInfo.Line.Trim())"
        )
    }

    if (-not [string]::IsNullOrWhiteSpace($ErrorRecord.ScriptStackTrace)) {
        Write-LogBlock -Title 'POWERSHELL STACK TRACE' -Lines @($ErrorRecord.ScriptStackTrace)
    }

    Write-Host ''
    Write-Host '============================================================================' -ForegroundColor Red
    Write-Host ' [ERROR] Release failed.' -ForegroundColor Red
    Write-Host '============================================================================' -ForegroundColor Red
    Write-Host "Current step: $script:CurrentStep"
    Write-Host "Message     : $($ErrorRecord.Exception.Message)"
    Write-Host "Log         : $ReleaseLog"
    Write-Host ''
}

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

$exitCode = 0

try {
    Open-ReleaseLog

    Write-Host ''
    Write-Host "Building $ProjectName $VersionString"
    Write-Host "Log: $ReleaseLog"
    Write-Host ''

    Test-ReleaseInputs
    Initialize-Dist
    Copy-RuntimeAndRootFiles
    Set-ReleaseRuntime
    Invoke-RegressionTest
    Invoke-DocumentationBuild
    Copy-SourceFiles
    New-ReleaseArchive

    Write-LogBlock -Title 'RELEASE COMPLETED' -Lines @(
        "Release directory: $ReleaseDir",
        "Release archive  : $OutputZip",
        "Log              : $ReleaseLog",
        "Completed        : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    )

    Write-Host ''
    Write-Host 'Release completed.'
    Write-Host "Release directory: $ReleaseDir"
    Write-Host "Release archive  : $OutputZip"
    Write-Host "Log              : $ReleaseLog"
    Write-Host ''

    if (Test-Path -LiteralPath $TempLogDir -PathType Container) {
        Remove-DirectoryIfExists $TempLogDir
    }
} catch {
    $exitCode = 1
    Write-FailureReport -ErrorRecord $_
} finally {
    Close-ReleaseLog
}

exit $exitCode
