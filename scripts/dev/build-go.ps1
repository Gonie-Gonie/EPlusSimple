[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$GoRuntimeFolderName = "GoV1-26-3",
    [string]$GoModuleRelativePath = "tools\go",
    [switch]$Tidy
)

Set-StrictMode -Version 1.0
$ErrorActionPreference = "Stop"

# -----------------------------------------------------------------------------
# Resolve repo root
# -----------------------------------------------------------------------------

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        throw "PSScriptRoot is empty. Run this script from a saved .ps1 file, not from a pasted selection."
    }

    # scripts/dev/build-go.ps1 -> repo root = ../..
    $RepoRoot = Join-Path $PSScriptRoot "..\.."
}

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

$RuntimeDir = Join-Path $RepoRoot "runtime"

$GoRootDir = Join-Path $RuntimeDir $GoRuntimeFolderName
$GoExe = Join-Path $GoRootDir "bin\go.exe"

$GoDataDir = Join-Path $RuntimeDir ".go"
$GoPathDir = Join-Path $GoDataDir "gopath"
$GoBuildCacheDir = Join-Path $GoDataDir "build-cache"
$GoModCacheDir = Join-Path $GoDataDir "mod-cache"

$GoModuleDir = Join-Path $RepoRoot $GoModuleRelativePath
$GoModFile = Join-Path $GoModuleDir "go.mod"

$RunEnginePackage = ".\cmd\runEngine"
$RunExcelLauncherPackage = ".\cmd\runExcelLauncher"

$RunEngineOutput = Join-Path $RepoRoot "EPlusSimpleCLI.exe"
$RunExcelLauncherOutput = Join-Path $RepoRoot "EPlusSimpleLauncher.exe"

# -----------------------------------------------------------------------------
# Validate
# -----------------------------------------------------------------------------

if (-not (Test-Path -LiteralPath $GoExe)) {
    throw "Go executable was not found: $GoExe"
}

if (-not (Test-Path -LiteralPath $GoModuleDir)) {
    throw "Go module directory was not found: $GoModuleDir"
}

if (-not (Test-Path -LiteralPath $GoModFile)) {
    throw "go.mod was not found: $GoModFile"
}

# -----------------------------------------------------------------------------
# Prepare Go environment
# -----------------------------------------------------------------------------

New-Item -ItemType Directory -Force -Path $GoPathDir | Out-Null
New-Item -ItemType Directory -Force -Path $GoBuildCacheDir | Out-Null
New-Item -ItemType Directory -Force -Path $GoModCacheDir | Out-Null

$env:GOROOT = $GoRootDir
$env:GOPATH = $GoPathDir
$env:GOCACHE = $GoBuildCacheDir
$env:GOMODCACHE = $GoModCacheDir
$env:GOTOOLCHAIN = "local"

$env:GOOS = "windows"
$env:GOARCH = "amd64"
$env:CGO_ENABLED = "0"

# Put repo-local Go first.
$env:PATH = "$(Split-Path -Parent $GoExe);$env:PATH"

Write-Host "=============================="
Write-Host "Building Go executables"
Write-Host "Repo root : $RepoRoot"
Write-Host "Go exe    : $GoExe"
Write-Host "Go module : $GoModuleDir"
Write-Host "=============================="

& $GoExe version

# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------

Push-Location $GoModuleDir

try {
    if ($Tidy) {
        Write-Host ""
        Write-Host "[tidy] go mod tidy"

        & $GoExe mod tidy

        if ($LASTEXITCODE -ne 0) {
            throw "go mod tidy failed with exit code $LASTEXITCODE"
        }
    }

    Write-Host ""
    Write-Host "[build] runEngine -> EPlusSimpleCLI.exe"

    if (Test-Path -LiteralPath $RunEngineOutput) {
        Remove-Item -LiteralPath $RunEngineOutput -Force
    }

    & $GoExe build `
        -trimpath `
        -ldflags "-s -w" `
        -o $RunEngineOutput `
        $RunEnginePackage

    if ($LASTEXITCODE -ne 0) {
        throw "go build failed for runEngine with exit code $LASTEXITCODE"
    }

    Write-Host ""
    Write-Host "[build] runExcelLauncher -> EPlusSimpleLauncher.exe"

    if (Test-Path -LiteralPath $RunExcelLauncherOutput) {
        Remove-Item -LiteralPath $RunExcelLauncherOutput -Force
    }

    & $GoExe build `
        -trimpath `
        -ldflags "-s -w" `
        -o $RunExcelLauncherOutput `
        $RunExcelLauncherPackage

    if ($LASTEXITCODE -ne 0) {
        throw "go build failed for runExcelLauncher with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "=============================="
Write-Host "Build completed successfully."
Write-Host "Generated:"
Write-Host " - $RunEngineOutput"
Write-Host " - $RunExcelLauncherOutput"
Write-Host "=============================="