# 공식 Stockfish 포터블 빌드를 engines\stockfish 에 받는다. (무료, GPLv3)
# 빌드/실행에 인터넷은 필요 없다. 이 스크립트는 엔진이 없을 때만 한 번 돌리면 된다.
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

$dest = "engines\stockfish"
$exe = Join-Path $dest "stockfish-windows-x86-64-universal.exe"
if (Test-Path $exe) {
    Write-Host "이미 있음: $exe"
    Pop-Location
    exit 0
}

$api = "https://api.github.com/repos/official-stockfish/Stockfish/releases/latest"
$release = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "chess-brain" }
$asset = $release.assets | Where-Object { $_.name -eq "stockfish-windows-x86-64-universal.zip" } | Select-Object -First 1
if (-not $asset) { throw "공식 릴리스에서 Windows 범용 빌드를 찾지 못했다." }

$tmp = Join-Path $env:TEMP "chess-brain-stockfish.zip"
Write-Host "받는 중: $($asset.name) ($([math]::Round($asset.size / 1MB))MB)"
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tmp -UseBasicParsing

$unpack = Join-Path $env:TEMP "chess-brain-stockfish-unpack"
if (Test-Path $unpack) { Remove-Item $unpack -Recurse -Force }
Expand-Archive -Path $tmp -DestinationPath $unpack -Force
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item (Join-Path $unpack "stockfish\*") $dest -Recurse -Force
Remove-Item $tmp -Force -ErrorAction SilentlyContinue
Remove-Item $unpack -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "완료: $exe"
Write-Host "라이선스: engines\stockfish\Copying.txt (GPLv3), 소스는 같은 폴더 src\ 포함"
Pop-Location
