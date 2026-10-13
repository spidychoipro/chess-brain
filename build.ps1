# chess-brain 실행 파일 빌드 (PyInstaller, onedir + windowed)
# onedir = 실행 시 매번 74MB 를 임시폴더에 풀지 않아서 시작이 빠르다.
# 결과: dist\chess-brain\chess-brain.exe  → 더블클릭으로 실행
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$py = "C:\Users\swpar\AppData\Local\Programs\Python\Python314\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "== PyInstaller 설치 =="
& $py -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pyinstaller 설치 실패" }

Write-Host "== 빌드 =="
& $py -m PyInstaller --noconfirm --clean --onedir --windowed --name chess-brain `
    --hidden-import googleapiclient `
    --hidden-import googleapiclient.discovery `
    --hidden-import googleapiclient.http `
    --hidden-import google_auth_oauthlib `
    --hidden-import google_auth_oauthlib.flow `
    --hidden-import google.auth `
    --hidden-import google.auth.transport `
    --hidden-import google.auth.transport.requests `
    --exclude-module tkinter `
    --exclude-module unittest `
    --exclude-module test `
    --exclude-module lib2to3 `
    --exclude-module curses `
    --exclude-module turtledemo `
    --exclude-module turtle `
    --exclude-module idlelib `
    --exclude-module pydoc `
    --exclude-module pydoc_data `
    --exclude-module doctest `
    --exclude-module ensurepip `
    --exclude-module venv `
    --exclude-module xmlrpc `
    main.py
if ($LASTEXITCODE -ne 0) { throw "빌드 실패" }

$exe = "dist\chess-brain\chess-brain.exe"
if (Test-Path $exe) {
    Write-Host "== 완료: $((Get-Item $exe).FullName) =="
    # 빌드본 자체 검증 (오프스creen 셀프테스트)
    Write-Host "== 셀프테스트 실행 =="
    $marker = Join-Path $env:TEMP "chess_brain_selftest_ok"
    Remove-Item $marker -ErrorAction SilentlyContinue
    $proc = Start-Process -FilePath $exe `
        -ArgumentList "--selftest" -Wait -PassThru
    $deadline = (Get-Date).AddSeconds(30)
    while (-not (Test-Path $marker) -and (Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
    }
    if ((Test-Path $marker) -and ($proc.ExitCode -eq 0)) {
        Write-Host "셀프테스트 통과"
    } else {
        throw "셀프테스트 실패: 마커 없음 (exit=$($proc.ExitCode))"
    }
} else {
    throw "$exe 가 생성되지 않음"
}

Pop-Location