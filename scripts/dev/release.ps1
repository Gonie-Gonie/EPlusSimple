# ============================================================================
# EPlusSimple release script
# ============================================================================
#
# Expected location:
# scripts/dev/release.ps1
#
# Intended caller:
# runscript.bat release ...
#
# This script creates a portable release package under:
# dist/EPlusSimple_V[R]/
# dist/EPlusSimple_V[R].zip
#
# Logging policy:
# - Detailed release log is written to:
#   logs/release.log
# - logs/release.log is overwritten on every release run.
# - Console output is intentionally kept concise.
#
# Runtime layout assumed by scripts/setup/setup.ps1:
# runtime/PythonV3-12-7/
# runtime/EnergyPlusV24-2-0/
# runtime/Weather/TMY/
# ============================================================================

[CmdletBinding()]
param(
    # Target distribution.
    # The KALIS package uses launcher/core.py and templates/.
    # The REB package additionally includes src/reb and uses core_reb.py.
    [Alias('For')]
    [ValidateSet('kalis', 'reb')]
    [string]$BuildFor = 'kalis',

    # Release version without leading V.
    [string]$Version = '0.6.1',

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
# Path configuration
# ----------------------------------------------------------------------------

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir '..\..')).Path

Set-Location $RepoRoot

$ProjectName = 'EPlusSimple'

$BuildFor = $BuildFor.ToLowerInvariant()

$VersionSuffix = ''
if ($BuildFor -eq 'reb') {
    $VersionSuffix = 'R'
}

$VersionString = "V$Version$VersionSuffix"
$ReleaseName = "$ProjectName`_$VersionString"

$DistDir = Join-Path $RepoRoot 'dist'
$ReleaseDir = Join-Path $DistDir $ReleaseName
$OutputZip = Join-Path $DistDir "$ReleaseName.zip"

$LogsDir = Join-Path $RepoRoot 'logs'
$ReleaseLog = Join-Path $LogsDir 'release.log'

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

$EnergyPlusPruneDirs = @(
    'DataSets',
    'Documentation',
    'ExampleFiles',
    'WeatherData',
    'MacroDataSets'
)

$ExamplesDir = Join-Path $RepoRoot 'examples'
$DocsDir = Join-Path $RepoRoot 'docs'
$SrcDir = Join-Path $RepoRoot 'src'

$RegressionTestScript = Join-Path $RepoRoot 'scripts\dev\regressiontest.py'
$RegressionLogLegacy = Join-Path $RepoRoot 'regtest.log'

$script:CurrentStep = 'initializing release script'

# ----------------------------------------------------------------------------
# Logging functions
# ----------------------------------------------------------------------------

function Ensure-Directory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Initialize-ReleaseLog {
    Ensure-Directory $LogsDir

    if (Test-Path -LiteralPath $ReleaseLog) {
        Remove-Item -LiteralPath $ReleaseLog -Force
    }

    $header = @(
        '============================================================================'
        ' EPlusSimple release log'
        '============================================================================'
        "Started      : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        "Repository   : $RepoRoot"
        "Target       : $BuildFor"
        "Version      : $VersionString"
        "Release dir  : $ReleaseDir"
        "Release zip  : $OutputZip"
        '============================================================================'
        ''
    )

    Set-Content -LiteralPath $ReleaseLog -Value $header -Encoding UTF8
}

function Write-Log {
    param([string]$Message)

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $ReleaseLog -Value "[$timestamp] $Message" -Encoding UTF8
}

function Write-LogBlock {
    param(
        [string]$Title,
        [string[]]$Lines = @()
    )

    Add-Content -LiteralPath $ReleaseLog -Value '' -Encoding UTF8
    Add-Content -LiteralPath $ReleaseLog -Value "===== $Title =====" -Encoding UTF8

    foreach ($line in $Lines) {
        Add-Content -LiteralPath $ReleaseLog -Value $line -Encoding UTF8
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
# Generic helper functions
# ----------------------------------------------------------------------------

function Remove-DirectoryIfExists {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        Write-Log "Removing directory: $Path"
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Remove-FileIfExists {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        Write-Log "Removing file: $Path"
        Remove-Item -LiteralPath $Path -Force
    }
}

function Assert-FileExists {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Message`nMissing file: $Path"
    }

    Write-Log "Validated file: $Path"
}

function Assert-DirectoryExists {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Message`nMissing directory: $Path"
    }

    Write-Log "Validated directory: $Path"
}

function ConvertTo-CommandLineArgument {
    param([string]$Value)

    if ($null -eq $Value) {
        return '""'
    }

    if ($Value -eq '') {
        return '""'
    }

    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    $escaped = $Value.Replace('"', '\"')
    return '"' + $escaped + '"'
}

function Invoke-LoggedCommand {
    param(
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = $RepoRoot,
        [string]$Description = 'external command'
    )

    $tempDir = Join-Path $LogsDir '_tmp_release'
    Ensure-Directory $tempDir

    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
    $safeName = ($Description -replace '[^a-zA-Z0-9_-]', '_')
    $stdoutLog = Join-Path $tempDir "$stamp`_$safeName.stdout.tmp"
    $stderrLog = Join-Path $tempDir "$stamp`_$safeName.stderr.tmp"

    Remove-FileIfExists $stdoutLog
    Remove-FileIfExists $stderrLog

    $argumentText = ($Arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join ' '
    $cmdText = "$FilePath $argumentText".Trim()

    Write-ProgressLine $Description

    Write-LogBlock -Title "COMMAND: $Description" -Lines @(
        "Working directory: $WorkingDirectory"
        "Command          : $cmdText"
    )

    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $argumentText `
        -WorkingDirectory $WorkingDirectory `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog

    $exitCode = $process.ExitCode
    if ($null -eq $exitCode) {
        $exitCode = 0
    }

    Write-LogBlock -Title "EXIT CODE: $Description" -Lines @([string]$exitCode)

    if (Test-Path -LiteralPath $stdoutLog) {
        $stdoutLines = Get-Content -LiteralPath $stdoutLog -ErrorAction SilentlyContinue
        Write-LogBlock -Title "STDOUT: $Description" -Lines @($stdoutLines)
    } else {
        Write-LogBlock -Title "STDOUT: $Description" -Lines @('(no stdout file)')
    }

    if (Test-Path -LiteralPath $stderrLog) {
        $stderrLines = Get-Content -LiteralPath $stderrLog -ErrorAction SilentlyContinue
        Write-LogBlock -Title "STDERR: $Description" -Lines @($stderrLines)
    } else {
        Write-LogBlock -Title "STDERR: $Description" -Lines @('(no stderr file)')
    }

    Remove-FileIfExists $stdoutLog
    Remove-FileIfExists $stderrLog

    if ($exitCode -ne 0) {
        throw "$Description failed. Exit code: $exitCode. See log: $ReleaseLog"
    }

    return $exitCode
}

function Copy-Directory {
    param(
        [string]$Source,
        [string]$Destination
    )

    Assert-DirectoryExists -Path $Source -Message 'Cannot copy directory because the source directory was not found.'

    Remove-DirectoryIfExists $Destination

    $parent = Split-Path -Parent $Destination
    Ensure-Directory $parent

    Write-Log "Copy directory: $Source -> $Destination"
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

function Copy-File {
    param(
        [string]$Source,
        [string]$Destination
    )

    Assert-FileExists -Path $Source -Message 'Cannot copy file because the source file was not found.'

    $parent = Split-Path -Parent $Destination
    Ensure-Directory $parent

    Write-Log "Copy file: $Source -> $Destination"
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Remove-EnergyPlusReleaseExtras {
    param([string]$ReleaseEnergyPlusDir)

    Assert-DirectoryExists -Path $ReleaseEnergyPlusDir -Message 'Release EnergyPlus runtime was not found.'

    Write-Log "Pruning EnergyPlus release directory: $ReleaseEnergyPlusDir"

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

function Add-UniqueLine {
    param(
        [string]$Path,
        [string]$Line
    )

    Assert-FileExists -Path $Path -Message 'Cannot update file because it was not found.'

    $lines = Get-Content -LiteralPath $Path -ErrorAction Stop

    if ($lines -contains $Line) {
        Write-Log "Already present in file: $Path :: $Line"
    } else {
        Add-Content -LiteralPath $Path -Value $Line
        Write-Log "Added to file: $Path :: $Line"
    }
}

# ----------------------------------------------------------------------------
# Release steps
# ----------------------------------------------------------------------------

function Validate-Inputs {
    Write-Step '[0/7] Validating release inputs...'

    Assert-DirectoryExists -Path $SrcDir -Message 'src directory was not found.'
    Assert-DirectoryExists -Path $ExamplesDir -Message 'examples directory was not found.'
    Assert-DirectoryExists -Path $DocsDir -Message 'docs directory was not found.'

    Assert-FileExists -Path $PythonExe -Message 'Python runtime was not found. Run "runscript setup" before release.'
    Assert-FileExists -Path $PythonPthFile -Message 'Python ._pth file was not found. Run "runscript setup" before release.'
    Assert-FileExists -Path $EnergyPlusExe -Message 'EnergyPlus runtime was not found. Run "runscript setup" before release.'
    Assert-DirectoryExists -Path $WeatherTmyDir -Message 'Korean TMY weather data was not found. Run "runscript setup" before release.'

    Assert-FileExists -Path $BuildGoScript -Message 'Go build script was not found.'
    Assert-DirectoryExists -Path (Join-Path $RepoRoot 'tools\go') -Message 'Go source directory was not found.'
    Assert-FileExists -Path (Join-Path $RepoRoot 'tools\go\go.mod') -Message 'Go module file was not found.'

    if (-not $SkipRegressionTest) {
        Assert-FileExists -Path $RegressionTestScript -Message 'Regression test script was not found.'
    }

    Write-LogBlock -Title 'RELEASE INPUTS' -Lines @(
        "Repository   : $RepoRoot"
        "Target       : $BuildFor"
        "Version      : $VersionString"
        "Python       : $PythonExe"
        "EnergyPlus   : $EnergyPlusExe"
        "Weather TMY  : $WeatherTmyDir"
        "Go build     : $BuildGoScript"
        "Skip docs    : $SkipDocs"
        "Skip regtest : $SkipRegressionTest"
        "No clean     : $NoClean"
    )
}

function Prepare-Dist {
    Write-Step '[1/7] Preparing dist directory...'

    if (-not $NoClean) {
        Remove-DirectoryIfExists $DistDir
    }

    Ensure-Directory $ReleaseDir

    Write-Log "Release directory prepared: $ReleaseDir"
}

function Build-GoLaunchers {
    Write-Log 'Building Go launchers.'

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
        -Description 'Go launcher build' | Out-Null

    Assert-FileExists -Path $EPlusSimpleCLIExe -Message 'EPlusSimpleCLI.exe was not generated by build-go.ps1.'
    Assert-FileExists -Path $EPlusSimpleLauncherExe -Message 'EPlusSimpleLauncher.exe was not generated by build-go.ps1.'

    Write-Log 'Go launchers built.'
}

function Copy-RuntimeAndRootFiles {
    Write-Step '[2/7] Copying runtime and root files...'

    $ReleaseRuntimeDir = Join-Path $ReleaseDir 'runtime'
    Ensure-Directory $ReleaseRuntimeDir

    Copy-Directory -Source $PythonDir -Destination (Join-Path $ReleaseRuntimeDir $PythonRuntimeName)

    $ReleaseEnergyPlusDir = Join-Path $ReleaseRuntimeDir $EnergyPlusRuntimeName
    Copy-Directory -Source $EnergyPlusDir -Destination $ReleaseEnergyPlusDir
    Remove-EnergyPlusReleaseExtras -ReleaseEnergyPlusDir $ReleaseEnergyPlusDir

    $ReleaseWeatherRootDir = Join-Path $ReleaseRuntimeDir $WeatherRuntimeName
    Ensure-Directory $ReleaseWeatherRootDir
    Copy-Directory -Source $WeatherTmyDir -Destination (Join-Path $ReleaseWeatherRootDir 'TMY')

    Copy-Directory -Source $ExamplesDir -Destination (Join-Path $ReleaseDir 'examples')

    Build-GoLaunchers

    Copy-File -Source $EPlusSimpleCLIExe -Destination (Join-Path $ReleaseDir 'EPlusSimpleCLI.exe')
    Copy-File -Source $EPlusSimpleLauncherExe -Destination (Join-Path $ReleaseDir 'EPlusSimpleLauncher.exe')

    Write-Log 'Runtime, weather data, examples, and root launchers copied.'
}

function Configure-ReleaseRuntime {
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
        "EPSIMPLE_RUNTIME_DIR    = $env:EPSIMPLE_RUNTIME_DIR"
        "IDRAGON_RUNTIME_DIR     = $env:IDRAGON_RUNTIME_DIR"
        "IDRAGON_ENERGYPLUS_DIR  = $env:IDRAGON_ENERGYPLUS_DIR"
        "ENERGYPLUS_DIR          = $env:ENERGYPLUS_DIR"
        "ENERGYPLUS_EXE          = $env:ENERGYPLUS_EXE"
        "EPSIMPLE_WEATHER_DIR    = $env:EPSIMPLE_WEATHER_DIR"
        "EPSIMPLE_TMY_DIR        = $env:EPSIMPLE_TMY_DIR"
        "PYTHONNOUSERSITE        = $env:PYTHONNOUSERSITE"
        "PATH head               = $($env:PATH.Split(';')[0])"
    )
}

function Run-RegressionTest {
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
        -Description 'Python version check' | Out-Null

    Invoke-LoggedCommand `
        -FilePath $EnergyPlusExe `
        -Arguments @('--version') `
        -WorkingDirectory $RepoRoot `
        -Description 'EnergyPlus version check' | Out-Null

    Invoke-LoggedCommand `
        -FilePath $PythonExe `
        -Arguments @($RegressionTestScript) `
        -WorkingDirectory $RepoRoot `
        -Description 'Regression test' | Out-Null

    if (Test-Path -LiteralPath $RegressionLogLegacy -PathType Leaf) {
        $regLines = Get-Content -LiteralPath $RegressionLogLegacy -ErrorAction SilentlyContinue
        Write-LogBlock -Title 'REGRESSION TEST LOG FILE: regtest.log' -Lines @($regLines)
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

function Build-AndCopyDoc {
    param(
        [string]$SourceName,
        [string]$DisplayName
    )

    $DocsBuildDir = Join-Path $DistDir 'docs'
    $ReleaseDocsDir = Join-Path $ReleaseDir 'docs'

    Ensure-Directory $DocsBuildDir
    Ensure-Directory $ReleaseDocsDir

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
        -Description "LaTeX build: $DisplayName" | Out-Null

    Assert-FileExists -Path $pdfFile -Message "Expected PDF was not generated for $DisplayName."

    Copy-File -Source $pdfFile -Destination $releasePdfFile
}

function Build-Documentation {
    if ($SkipDocs) {
        Write-Step '[5/7] Skipping documentation build.'
        return
    }

    Write-Step '[5/7] Building documentation...'

    Write-ReleaseInfo

    Build-AndCopyDoc -SourceName 'mainTRM' -DisplayName 'Technical Reference Manual'
    Build-AndCopyDoc -SourceName 'mainRTR' -DisplayName 'Regression Test Report'
    Build-AndCopyDoc -SourceName 'mainRN' -DisplayName 'Release Note'

    Write-Log 'Documentation build completed.'
}

function Copy-SourceForTarget {
    Write-Step '[6/7] Copying source files and launcher configuration...'

    $ReleaseSrcDir = Join-Path $ReleaseDir 'src'
    Ensure-Directory $ReleaseSrcDir

    Copy-Directory -Source (Join-Path $SrcDir 'epsimple') -Destination (Join-Path $ReleaseSrcDir 'epsimple')
    Copy-Directory -Source (Join-Path $SrcDir 'idragon') -Destination (Join-Path $ReleaseSrcDir 'idragon')

    $LauncherSrcDir = Join-Path $SrcDir 'launcher'
    $LauncherReleaseDir = Join-Path $ReleaseSrcDir 'launcher'

    Ensure-Directory $LauncherReleaseDir

    Copy-Directory -Source (Join-Path $LauncherSrcDir 'static') -Destination (Join-Path $LauncherReleaseDir 'static')
    Copy-File -Source (Join-Path $LauncherSrcDir '__init__.py') -Destination (Join-Path $LauncherReleaseDir '__init__.py')
    Copy-File -Source (Join-Path $LauncherSrcDir '__main__.py') -Destination (Join-Path $LauncherReleaseDir '__main__.py')

    $configPath = Join-Path $LauncherReleaseDir 'config.py'

    if ($BuildFor -eq 'kalis') {
        Write-Log 'Configuring launcher for KALIS.'

        Copy-Directory -Source (Join-Path $LauncherSrcDir 'templates') -Destination (Join-Path $LauncherReleaseDir 'templates')
        Copy-File -Source (Join-Path $LauncherSrcDir 'core.py') -Destination (Join-Path $LauncherReleaseDir 'core.py')

        @"
TEMPLATE_DIRNAME = "templates"
COREMODULE_NAME = "core"
"@ | Set-Content -LiteralPath $configPath -Encoding UTF8
    } elseif ($BuildFor -eq 'reb') {
        Write-Log 'Configuring launcher for REB.'

        Copy-Directory -Source (Join-Path $SrcDir 'reb') -Destination (Join-Path $ReleaseSrcDir 'reb')
        Copy-Directory -Source (Join-Path $LauncherSrcDir 'templates_reb') -Destination (Join-Path $LauncherReleaseDir 'templates_reb')
        Copy-File -Source (Join-Path $LauncherSrcDir 'core_reb.py') -Destination (Join-Path $LauncherReleaseDir 'core_reb.py')

        @"
TEMPLATE_DIRNAME = "templates_reb"
COREMODULE_NAME = "core_reb"
"@ | Set-Content -LiteralPath $configPath -Encoding UTF8
    } else {
        throw "Invalid build target: $BuildFor"
    }

    Write-Log "Source copied for target: $BuildFor"
}

function Create-Archive {
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
        -Description 'Archive creation' | Out-Null

    Assert-FileExists -Path $OutputZip -Message 'Release zip was not created.'

    Write-Log "Archive created: $OutputZip"
}

function Write-FailureReport {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)

    Write-LogBlock -Title 'RELEASE FAILED' -Lines @(
        "Current step: $script:CurrentStep"
        "Exception type: $($ErrorRecord.Exception.GetType().FullName)"
        "Message: $($ErrorRecord.Exception.Message)"
    )

    if ($null -ne $ErrorRecord.InvocationInfo) {
        Write-LogBlock -Title 'FAILURE LOCATION' -Lines @(
            "Script : $($ErrorRecord.InvocationInfo.ScriptName)"
            "Line   : $($ErrorRecord.InvocationInfo.ScriptLineNumber)"
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

try {
    Initialize-ReleaseLog

    Write-Host ''
    Write-Host "Building $ProjectName $VersionString for [$BuildFor]"
    Write-Host "Log: $ReleaseLog"
    Write-Host ''

    Validate-Inputs
    Prepare-Dist
    Copy-RuntimeAndRootFiles
    Configure-ReleaseRuntime
    Run-RegressionTest
    Build-Documentation
    Copy-SourceForTarget
    Create-Archive

    Write-LogBlock -Title 'RELEASE COMPLETED' -Lines @(
        "Release directory: $ReleaseDir"
        "Release archive  : $OutputZip"
        "Log              : $ReleaseLog"
        "Completed        : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    )

    Write-Host ''
    Write-Host 'Release completed.'
    Write-Host "Release directory: $ReleaseDir"
    Write-Host "Release archive  : $OutputZip"
    Write-Host "Log              : $ReleaseLog"
    Write-Host ''

    $tmpDir = Join-Path $LogsDir '_tmp_release'
    if (Test-Path -LiteralPath $tmpDir) {
        Remove-DirectoryIfExists $tmpDir
    }

    exit 0
} catch {
    Write-FailureReport -ErrorRecord $_
    exit 1
}
