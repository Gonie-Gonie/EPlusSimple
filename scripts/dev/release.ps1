# ============================================================================
# EPlusSimple release script
# ============================================================================
#
# Expected location:
#   scripts/dev/release.ps1
#
# Intended caller:
#   scripts/dev/release.bat
#
# This script creates a portable release package under:
#   dist/EPlusSimple_V[R]/
#   dist/EPlusSimple_V[R].zip
#
# Runtime layout assumed by setup.ps1:
#   runtime/PythonV3-12-7/
#   runtime/EnergyPlusV24-2-0/
#
# Design notes:
# - release.bat should remain a small Windows wrapper.
# - This PowerShell file owns the actual release logic.
# - All paths are resolved relative to the repository root.
# - setup download caches are not copied into the release package.
# - Root launchers are now built from Go sources by scripts/dev/build-go.ps1.
# ============================================================================

[CmdletBinding()]
param(
    # Target distribution. The KALIS package uses launcher/core.py and templates/.
    # The REB package additionally includes src/reb and uses core_reb.py.
    [Alias('For')]
    [ValidateSet('kalis', 'reb')]
    [string]$BuildFor = 'kalis',

    # Release version without leading V.
    [string]$Version = '0.6.1',

    # Skip regression only when iterating on packaging logic.
    # Normal releases should keep regression enabled.
    [switch]$SkipRegressionTest,

    # Skip documentation build when latexmk is not available or when testing
    # packaging-only changes.
    [switch]$SkipDocs,

    # Keep the existing dist directory. This is useful for debugging but should
    # not be used for normal releases because stale files can remain.
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

# Keep every relative path stable regardless of where release.bat was invoked.
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

# Logs are placed outside the release directory so they are not included in the
# final archive. They are still kept under dist because they are build artifacts.
$ReleaseLogDir = Join-Path $DistDir '_release_logs'
$ReleaseSummaryLog = Join-Path $ReleaseLogDir 'release-summary.log'

$RuntimeDir = Join-Path $RepoRoot 'runtime'

$PythonRuntimeName = 'PythonV3-12-7'
$EnergyPlusRuntimeName = 'EnergyPlusV24-2-0'

$PythonDir = Join-Path $RuntimeDir $PythonRuntimeName
$PythonExe = Join-Path $PythonDir 'python.exe'
$PythonPthFileName = 'python312._pth'
$PythonPthFile = Join-Path $PythonDir $PythonPthFileName

$EnergyPlusDir = Join-Path $RuntimeDir $EnergyPlusRuntimeName
$EnergyPlusExe = Join-Path $EnergyPlusDir 'energyplus.exe'

# Go launcher build.
$BuildGoScript = Join-Path $RepoRoot 'scripts\dev\build-go.ps1'
$EPlusSimpleExe = Join-Path $RepoRoot 'EPlusSimple.exe'
$EPlusSimpleLauncherExe = Join-Path $RepoRoot 'EPlusSimpleLauncher.exe'

# Folders that are useful in a full EnergyPlus installation but are not needed
# for the packaged EPlusSimple runtime.
#
# DataSets      : library IDF snippets for model authors
# Documentation : local EnergyPlus manuals
# ExampleFiles  : sample IDF/output files
# WeatherData   : sample EPW/DDY files; EPlusSimple supplies/uses its own weather files
# MacroDataSets : macro-oriented data snippets; not needed unless users rely on EP-Macro libraries
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
$RegressionLog = Join-Path $RepoRoot 'regtest.log'

# Current step and command logs are used by the catch block. This keeps error
# reporting centralized and avoids writing regression-specific diagnostics only.
$script:CurrentStep = 'initializing release script'
$script:CommandLogs = New-Object System.Collections.Generic.List[string]

# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------

function Write-Section {
    param([string]$Message)

    Write-Host ''
    Write-Host '============================================================================'
    Write-Host " $Message"
    Write-Host '============================================================================'
}

function Write-Step {
    param([string]$Message)

    $script:CurrentStep = $Message
    Write-Host $Message
}

function Ensure-Directory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Remove-DirectoryIfExists {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Remove-FileIfExists {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
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
}

function Assert-DirectoryExists {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Message`nMissing directory: $Path"
    }
}

function Register-CommandLog {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    if (-not $script:CommandLogs.Contains($Path)) {
        $script:CommandLogs.Add($Path) | Out-Null
    }
}

function Write-LogTail {
    param(
        [string]$Path,
        [int]$Tail = 80
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    Write-Host ''
    Write-Host ("Last {0} lines of {1}:" -f $Tail, $Path)
    Write-Host '----------------------------------------------------------------------------'
    Get-Content -LiteralPath $Path -Tail $Tail
    Write-Host '----------------------------------------------------------------------------'
}

function ConvertTo-CommandLineArgument {
    param([string]$Value)

    # Start-Process receives a single command-line string on Windows.
    # Therefore each argument must be quoted explicitly when it contains
    # whitespace or special characters.
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
        [string]$LogPath,
        [string]$WorkingDirectory = $RepoRoot,
        [string]$Description = 'external command'
    )

    # Do not use:
    #   & $FilePath @Arguments *> $LogPath
    #
    # In Windows PowerShell, native stderr can be converted into ErrorRecord
    # objects. If $ErrorActionPreference is 'Stop', ordinary stderr output
    # from tools can terminate the release script even when the process exit
    # code is 0.
    #
    # Start-Process with RedirectStandardOutput/RedirectStandardError avoids
    # that problem. It treats stdout/stderr as process streams and lets us judge
    # success only by the real process exit code.

    $logParent = Split-Path -Parent $LogPath
    Ensure-Directory $logParent
    Register-CommandLog $LogPath

    $stdoutLog = "$LogPath.stdout.tmp"
    $stderrLog = "$LogPath.stderr.tmp"

    Remove-FileIfExists $LogPath
    Remove-FileIfExists $stdoutLog
    Remove-FileIfExists $stderrLog

    $argumentText = ($Arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join ' '
    $cmdText = "$FilePath $argumentText".Trim()

    Write-Host " ...Running: $Description"
    Write-Host " Command : $cmdText"
    Write-Host " Log     : $LogPath"

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

    # Create a single combined log file. Keeping stdout/stderr separated in the
    # log makes it easier to identify progress messages, warnings, and errors.
    $logLines = New-Object System.Collections.Generic.List[string]

    $logLines.Add("===== COMMAND =====")
    $logLines.Add($cmdText)
    $logLines.Add("")
    $logLines.Add("===== EXIT CODE =====")
    $logLines.Add([string]$exitCode)
    $logLines.Add("")
    $logLines.Add("===== STDOUT =====")

    if (Test-Path -LiteralPath $stdoutLog) {
        $stdoutLines = Get-Content -LiteralPath $stdoutLog -ErrorAction SilentlyContinue
        if ($null -ne $stdoutLines) {
            foreach ($line in @($stdoutLines)) {
                [void]$logLines.Add([string]$line)
            }
        }
    }

    $logLines.Add("")
    $logLines.Add("===== STDERR =====")

    if (Test-Path -LiteralPath $stderrLog) {
        $stderrLines = Get-Content -LiteralPath $stderrLog -ErrorAction SilentlyContinue
        if ($null -ne $stderrLines) {
            foreach ($line in @($stderrLines)) {
                [void]$logLines.Add([string]$line)
            }
        }
    }

    Set-Content -LiteralPath $LogPath -Value $logLines -Encoding UTF8

    Remove-FileIfExists $stdoutLog
    Remove-FileIfExists $stderrLog

    if ($null -eq $exitCode) {
        $exitCode = 0
    }

    if ($exitCode -ne 0) {
        Write-LogTail -Path $LogPath -Tail 120
        throw "$Description failed. Exit code: $exitCode. Log: $LogPath"
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

    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Remove-EnergyPlusReleaseExtras {
    param([string]$ReleaseEnergyPlusDir)

    # Keep setup/runtime/EnergyPlusV... intact. This function operates only on
    # dist/.../runtime/EnergyPlusV..., after the runtime has been copied into
    # the release directory.
    Assert-DirectoryExists -Path $ReleaseEnergyPlusDir -Message 'Release EnergyPlus runtime was not found.'

    Write-Host ' ...Removing non-runtime EnergyPlus folders from release copy.'

    foreach ($dirname in $EnergyPlusPruneDirs) {
        $target = Join-Path $ReleaseEnergyPlusDir $dirname

        if (Test-Path -LiteralPath $target -PathType Container) {
            Remove-DirectoryIfExists $target
            Write-Host "    Removed: $dirname"
        } else {
            Write-Host "    Not found, skipped: $dirname"
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
        Write-Host " ...Already present: $Line"
    } else {
        Add-Content -LiteralPath $Path -Value $Line
        Write-Host " ...Added: $Line"
    }
}

function Write-ReleaseSummary {
    param([string]$Message)

    Ensure-Directory $ReleaseLogDir

    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $ReleaseSummaryLog -Value "[$timestamp] $Message"
}

# ----------------------------------------------------------------------------
# Release steps
# ----------------------------------------------------------------------------

function Validate-Inputs {
    Write-Step '[0/7] Validating release inputs...'

    Assert-DirectoryExists -Path $SrcDir -Message 'src directory was not found.'
    Assert-DirectoryExists -Path $ExamplesDir -Message 'examples directory was not found.'
    Assert-DirectoryExists -Path $DocsDir -Message 'docs directory was not found.'

    Assert-FileExists -Path $PythonExe -Message 'Python runtime was not found. Run setup.bat before release.'
    Assert-FileExists -Path $PythonPthFile -Message 'Python ._pth file was not found. Run setup.bat before release.'

    Assert-FileExists -Path $EnergyPlusExe -Message 'EnergyPlus runtime was not found. Run setup.bat before release.'

    Assert-FileExists -Path $BuildGoScript -Message 'Go build script was not found.'
    Assert-DirectoryExists -Path (Join-Path $RepoRoot 'tools\go') -Message 'Go source directory was not found.'
    Assert-FileExists -Path (Join-Path $RepoRoot 'tools\go\go.mod') -Message 'Go module file was not found.'

    if (-not $SkipRegressionTest) {
        Assert-FileExists -Path $RegressionTestScript -Message 'Regression test script was not found.'
    }

    Write-Host " ...Repository : $RepoRoot"
    Write-Host " ...Target     : $BuildFor"
    Write-Host " ...Version    : $VersionString"
    Write-Host " ...Python     : $PythonExe"
    Write-Host " ...EnergyPlus : $EnergyPlusExe"
    Write-Host " ...Go build   : $BuildGoScript"
}

function Prepare-Dist {
    Write-Step '[1/7] Preparing dist directory...'

    if (-not $NoClean) {
        Remove-DirectoryIfExists $DistDir
    }

    Ensure-Directory $ReleaseDir
    Ensure-Directory $ReleaseLogDir

    Remove-FileIfExists $ReleaseSummaryLog

    Write-ReleaseSummary "Release started: $ReleaseName"
    Write-ReleaseSummary "Repository: $RepoRoot"
    Write-ReleaseSummary "Target: $BuildFor"
    Write-ReleaseSummary "Python: $PythonExe"
    Write-ReleaseSummary "EnergyPlus: $EnergyPlusExe"
}

function Build-GoLaunchers {
    Write-Host ' ...Building Go launchers.'

    $goBuildLog = Join-Path $ReleaseLogDir 'go-build.log'

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
        -LogPath $goBuildLog `
        -WorkingDirectory $RepoRoot `
        -Description 'Go launcher build' | Out-Null

    Assert-FileExists -Path $EPlusSimpleExe -Message 'EPlusSimple.exe was not generated by build-go.ps1.'
    Assert-FileExists -Path $EPlusSimpleLauncherExe -Message 'EPlusSimpleLauncher.exe was not generated by build-go.ps1.'

    Write-ReleaseSummary 'Go launchers built.'
}

function Copy-RuntimeAndRootFiles {
    Write-Step '[2/7] Copying runtime and root files...'

    $ReleaseRuntimeDir = Join-Path $ReleaseDir 'runtime'
    Ensure-Directory $ReleaseRuntimeDir

    # Copy only the runtime components required by the distribution.
    # runtime/downloads and runtime/_energyplus_extract are intentionally not
    # copied because they are setup caches, not runtime dependencies.
    Copy-Directory -Source $PythonDir -Destination (Join-Path $ReleaseRuntimeDir $PythonRuntimeName)

    $ReleaseEnergyPlusDir = Join-Path $ReleaseRuntimeDir $EnergyPlusRuntimeName
    Copy-Directory -Source $EnergyPlusDir -Destination $ReleaseEnergyPlusDir
    Remove-EnergyPlusReleaseExtras -ReleaseEnergyPlusDir $ReleaseEnergyPlusDir

    # examples/ is currently part of the user-facing distribution.
    Copy-Directory -Source $ExamplesDir -Destination (Join-Path $ReleaseDir 'examples')

    # Build native Go launchers and place them at release root.
    # Replaces the previous runEngine.bat / runExcelLauncher.bat copy step.
    Build-GoLaunchers

    Copy-File -Source $EPlusSimpleExe -Destination (Join-Path $ReleaseDir 'EPlusSimple.exe')
    Copy-File -Source $EPlusSimpleLauncherExe -Destination (Join-Path $ReleaseDir 'EPlusSimpleLauncher.exe')

    Write-ReleaseSummary 'Runtime and root launchers copied.'
}

function Configure-ReleaseRuntime {
    Write-Step '[3/7] Configuring release runtime paths...'

    $ReleasePthFile = Join-Path $ReleaseDir "runtime\$PythonRuntimeName\$PythonPthFileName"

    # python312._pth is located in:
    #   release/runtime/PythonV3-12-7/python312._pth
    #
    # The source package directory is:
    #   release/src
    #
    # Therefore, the correct relative path is:
    #   ..\..\src
    #
    # Lib\site-packages and import site are required for packages installed by
    # pip into the embedded Python runtime.
    Add-UniqueLine -Path $ReleasePthFile -Line 'Lib\site-packages'
    Add-UniqueLine -Path $ReleasePthFile -Line '..\..\src'
    Add-UniqueLine -Path $ReleasePthFile -Line 'import site'

    Write-ReleaseSummary 'Release runtime paths configured.'
}

function Set-ReleaseEnvironment {
    # These variables let epsimple/idragon find the repository runtime while the
    # codebase is being refactored away from hard-coded runtime locations.
    # They are set here before running regression tests.

    $env:EPSIMPLE_RUNTIME_DIR = $RuntimeDir
    $env:IDRAGON_RUNTIME_DIR = $RuntimeDir
    $env:IDRAGON_ENERGYPLUS_DIR = $EnergyPlusDir
    $env:ENERGYPLUS_DIR = $EnergyPlusDir
    $env:ENERGYPLUS_EXE = $EnergyPlusExe
    $env:PATH = "$EnergyPlusDir;$env:PATH"
}

function Run-RegressionTest {
    if ($SkipRegressionTest) {
        Write-Step '[4/7] Skipping regression test.'
        Write-ReleaseSummary 'Regression test skipped.'
        return
    }

    Write-Step '[4/7] Running regression test...'

    Set-ReleaseEnvironment

    Write-Host " ...Working dir       : $RepoRoot"
    Write-Host " ...Python exe        : $PythonExe"
    Write-Host " ...Regression script : $RegressionTestScript"
    Write-Host " ...Regression log    : $RegressionLog"
    Write-Host " ...Runtime dir       : $RuntimeDir"
    Write-Host " ...EnergyPlus dir    : $EnergyPlusDir"
    Write-Host " ...PATH head         : $($env:PATH.Split(';')[0])"

    $pythonVersionLog = Join-Path $ReleaseLogDir 'python-version.log'
    $epVersionLog = Join-Path $ReleaseLogDir 'energyplus-version.log'

    Invoke-LoggedCommand `
        -FilePath $PythonExe `
        -Arguments @('--version') `
        -LogPath $pythonVersionLog `
        -WorkingDirectory $RepoRoot `
        -Description 'Python version check' | Out-Null

    Invoke-LoggedCommand `
        -FilePath $EnergyPlusExe `
        -Arguments @('--version') `
        -LogPath $epVersionLog `
        -WorkingDirectory $RepoRoot `
        -Description 'EnergyPlus version check' | Out-Null

    # Keep the regression invocation intentionally close to the manual command:
    #   runtime\PythonV3-12-7\python.exe scripts\dev\regressiontest.py
    Invoke-LoggedCommand `
        -FilePath $PythonExe `
        -Arguments @($RegressionTestScript) `
        -LogPath $RegressionLog `
        -WorkingDirectory $RepoRoot `
        -Description 'Regression test' | Out-Null

    Write-ReleaseSummary 'Regression test passed.'
}

function Write-ReleaseInfo {
    $today = Get-Date -Format 'yyyy.MM.dd.'
    $releaseInfoPath = Join-Path $DocsDir 'releaseinfo.tex'

@"
\newcommand{\releaseversion}{$VersionString}
\newcommand{\releasedate}{$today}
"@ | Set-Content -LiteralPath $releaseInfoPath -Encoding UTF8

    Write-Host " ...Updated: $releaseInfoPath"
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
    $latexLog = Join-Path $ReleaseLogDir "latex-$SourceName.log"

    # latexmk is executed from docs/ so relative paths inside .tex files keep the
    # same meaning as the previous release.bat workflow.
    Invoke-LoggedCommand `
        -FilePath 'latexmk' `
        -Arguments @('-silent', '-pdf', '-outdir=../dist/docs', $texFile) `
        -LogPath $latexLog `
        -WorkingDirectory $DocsDir `
        -Description "LaTeX build: $DisplayName" | Out-Null

    Assert-FileExists -Path $pdfFile -Message "Expected PDF was not generated for $DisplayName."

    Copy-File -Source $pdfFile -Destination $releasePdfFile
}

function Build-Documentation {
    if ($SkipDocs) {
        Write-Step '[5/7] Skipping documentation build.'
        Write-ReleaseSummary 'Documentation build skipped.'
        return
    }

    Write-Step '[5/7] Building documentation...'

    Write-ReleaseInfo

    Build-AndCopyDoc -SourceName 'mainTRM' -DisplayName 'Technical Reference Manual'
    Build-AndCopyDoc -SourceName 'mainRTR' -DisplayName 'Regression Test Report'
    Build-AndCopyDoc -SourceName 'mainRN' -DisplayName 'Release Note'

    Write-ReleaseSummary 'Documentation build completed.'
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
        Write-Host ' ...Configuring launcher for KALIS.'

        Copy-Directory -Source (Join-Path $LauncherSrcDir 'templates') -Destination (Join-Path $LauncherReleaseDir 'templates')
        Copy-File -Source (Join-Path $LauncherSrcDir 'core.py') -Destination (Join-Path $LauncherReleaseDir 'core.py')

@"
TEMPLATE_DIRNAME = "templates"
COREMODULE_NAME = "core"
"@ | Set-Content -LiteralPath $configPath -Encoding UTF8

    } elseif ($BuildFor -eq 'reb') {
        Write-Host ' ...Configuring launcher for REB.'

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

    Write-ReleaseSummary "Source copied for target: $BuildFor"
}

function Create-Archive {
    Write-Step '[7/7] Creating release zip...'

    Remove-FileIfExists $OutputZip

    $archiveLog = Join-Path $ReleaseLogDir 'archive.log'

    # Keep the previous release.bat behavior:
    # the zip contains the contents of EPlusSimple_V..., not an extra parent
    # folder. This means users can unzip directly into the application folder.
    Invoke-LoggedCommand `
        -FilePath 'tar' `
        -Arguments @('-a', '-c', '-f', $OutputZip, '.') `
        -LogPath $archiveLog `
        -WorkingDirectory $ReleaseDir `
        -Description 'Archive creation' | Out-Null

    Assert-FileExists -Path $OutputZip -Message 'Release zip was not created.'

    Write-Host " ...Created: $OutputZip"
    Write-ReleaseSummary "Archive created: $OutputZip"
}

function Write-FailureReport {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)

    Write-Host ''
    Write-Host '============================================================================' -ForegroundColor Red
    Write-Host ' [ERROR] Release failed.' -ForegroundColor Red
    Write-Host '============================================================================' -ForegroundColor Red
    Write-Host ''

    Write-Host 'Current step:'
    Write-Host "  $script:CurrentStep"
    Write-Host ''

    Write-Host 'Exception:'
    Write-Host "  Type   : $($ErrorRecord.Exception.GetType().FullName)"
    Write-Host "  Message: $($ErrorRecord.Exception.Message)"
    Write-Host ''

    if ($null -ne $ErrorRecord.InvocationInfo) {
        Write-Host 'Location:'
        Write-Host "  Script : $($ErrorRecord.InvocationInfo.ScriptName)"
        Write-Host "  Line   : $($ErrorRecord.InvocationInfo.ScriptLineNumber)"
        Write-Host "  Command: $($ErrorRecord.InvocationInfo.Line.Trim())"
        Write-Host ''
    }

    if (-not [string]::IsNullOrWhiteSpace($ErrorRecord.ScriptStackTrace)) {
        Write-Host 'PowerShell stack trace:'
        Write-Host $ErrorRecord.ScriptStackTrace
        Write-Host ''
    }

    foreach ($logPath in $script:CommandLogs) {
        Write-LogTail -Path $logPath -Tail 80
    }

    Write-Host ''
    Write-Host 'Suggested checks:'
    Write-Host '  1. Confirm setup.bat completed and runtime folders exist.'
    Write-Host '  2. Confirm runtime\GoV1-26-3\bin\go.exe exists.'
    Write-Host '  3. Confirm scripts\dev\build-go.ps1 works when run manually.'
    Write-Host '  4. Check the current step above; it usually identifies the failing phase.'
    Write-Host '  5. Check the log tails printed above for native command failures.'
    Write-Host '  6. If documentation failed, verify latexmk is available in PATH.'
    Write-Host '  7. If regression failed, compare regtest.log with a manual run.'
    Write-Host ''
}

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

try {
    Write-Section "Building $ProjectName $VersionString for [$BuildFor]"

    Validate-Inputs
    Prepare-Dist
    Copy-RuntimeAndRootFiles
    Configure-ReleaseRuntime
    Run-RegressionTest
    Build-Documentation
    Copy-SourceForTarget
    Create-Archive

    Write-Section 'Distribution packaging complete'
    Write-Host "Release directory : $ReleaseDir"
    Write-Host "Release archive   : $OutputZip"
    Write-Host "Release logs      : $ReleaseLogDir"
    Write-Host ''

    exit 0
}
catch {
    Write-FailureReport -ErrorRecord $_
    exit 1
}