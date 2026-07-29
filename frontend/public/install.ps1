# Vibecell CLI installer for Windows.
#
# Usage:
#   iwr -useb https://vibecell.dev/install.ps1 | iex
#
# Environment overrides:
#   HANGAR_BASE_URL     — base URL to fetch from (default: https://vibecell.dev)
#   HANGAR_INSTALL_DIR  — directory to install into (default: $env:USERPROFILE\.hangar\bin)

$ErrorActionPreference = "Stop"

$BaseUrl = if ($env:HANGAR_BASE_URL) { $env:HANGAR_BASE_URL } else { "https://vibecell.dev" }
$Target  = "x86_64-pc-windows-msvc"
$InstallDir = if ($env:HANGAR_INSTALL_DIR) { $env:HANGAR_INSTALL_DIR } else { "$env:USERPROFILE\.hangar\bin" }

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$Url = "$($BaseUrl.TrimEnd('/'))/releases/hangar-$Target.zip"
$Tmp = New-TemporaryFile
$ZipPath = "$Tmp.zip"

Write-Host "==> downloading $Url"
Invoke-WebRequest -Uri $Url -OutFile $ZipPath

Write-Host "==> extracting to $InstallDir"
Expand-Archive -Force -Path $ZipPath -DestinationPath $InstallDir
Remove-Item $ZipPath -Force
Remove-Item $Tmp -Force

Write-Host ""
Write-Host "ok installed to $InstallDir\hangar.exe"

$paths = ($env:Path -split ';')
if ($paths -notcontains $InstallDir) {
    Write-Host "   add $InstallDir to your PATH (User scope):"
    Write-Host "     [Environment]::SetEnvironmentVariable('Path', `"$InstallDir;`" + [Environment]::GetEnvironmentVariable('Path','User'), 'User')"
} else {
    Write-Host "   $InstallDir is already in PATH — you're done."
}

Write-Host ""

# One-line setup path — see the matching comment in install.sh.
if ($env:HANGAR_SETUP_CODE) {
    Write-Host "==> pairing this device and configuring your MCP clients"
    & "$InstallDir\hangar.exe" setup --code $env:HANGAR_SETUP_CODE
    if ($LASTEXITCODE -eq 0) { exit 0 }
    Write-Host ""
    Write-Warning "automatic setup unavailable in this build - falling back"
}

Write-Host "next: run ``hangar pair`` to connect this device."
