# Installs the latest ipsubnet binary for Windows.
#   irm https://raw.githubusercontent.com/ShazanZaidii/ipsubnet/main/scripts/install.ps1 | iex
$ErrorActionPreference = "Stop"

$repo = "ShazanZaidii/ipsubnet"
$url  = "https://github.com/$repo/releases/latest/download/ipsubnet-windows-x64.exe"
$dir  = Join-Path $env:LOCALAPPDATA "Programs\ipsubnet"
$exe  = Join-Path $dir "ipsubnet.exe"

New-Item -ItemType Directory -Force -Path $dir | Out-Null
Write-Host "Downloading $url"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not ($userPath -split ";" | Where-Object { $_ -eq $dir })) {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$dir", "User")
    Write-Host "Added $dir to your PATH. Open a new terminal to use 'ipsubnet'."
}
$env:Path = "$env:Path;$dir"
Write-Host "Installed: $exe"
& $exe --version
