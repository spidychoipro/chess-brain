# chess-brain 실행 파일 빌드 (PyInstaller, onedir + windowed)
# onedir = 실행 시 매번 74MB 를 임시폴더에 풀지 않아서 시작이 빠르다.
# 결과: dist\chess-brain\chess-brain.exe  → 더블클릭으로 실행
#
# 주의: PyInstaller --noconfirm 은 출력 폴더(dist\chess-brain)를 통째로 지운다.
#   그 안에 사용자 설정(config\config.json, token.json ...)과 학습 DB(data\app.db)가
#   같이 들어 있어서, 그냥 빌드하면 설정과 복습 기록이 매번 날아간다.
#   그래서 빌드 전에 백업했다가 빌드 후 되돌린다.
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$py = "C:\Users\swpar\AppData\Local\Programs\Python\Python314\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

$out = "dist\chess-brain"
$keep = Join-Path $env:TEMP "chess-brain-keep"

# -- 빌드 전: 사용자 설정/DB 백업 -------------------------------------------
if (Test-Path $keep) { Remove-Item $keep -Recurse -Force }
New-Item -ItemType Directory -Force -Path $keep | Out-Null
$saved = @()
foreach ($sub in @("config", "data")) {
    $src = Join-Path $out $sub
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $keep $sub) -Recurse -Force
        $saved += $sub
    }
}
if ($saved.Count -gt 0) {
    Write-Host "== 기존 설정/DB 백업: $($saved -join ', ') =="
}

Write-Host "== PyInstaller 설치 =="
& $py -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pyinstaller 설치 실패" }

try {
    Write-Host "== 빌드 =="
    # 주의: unittest 는 절대 제외하지 말 것.
    #   googleapiclient -> httplib2 -> pyparsing -> pyparsing.testing 이 import 시점에
    #   unittest 를 끌어온다. 빼면 드라이브/로컬 동기화가 "No module named 'unittest'" 로 깨진다.
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
        --exclude-module lib2to3 `
        --exclude-module test `
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

    # -- 빌드 후: 백업한 설정/DB 복원 (셀프테스트보다 먼저) -------------------
    foreach ($sub in @("config", "data")) {
        $bk = Join-Path $keep $sub
        if (Test-Path $bk) {
            $dst = Join-Path $out $sub
            New-Item -ItemType Directory -Force -Path $dst | Out-Null
            Copy-Item (Join-Path $bk "*") $dst -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    if ($saved.Count -gt 0) {
        Write-Host "== 설정/DB 복원 완료 =="
    }

    $exe = "dist\chess-brain\chess-brain.exe"
    if (Test-Path $exe) {
        Write-Host "== 완료: $((Get-Item $exe).FullName) =="
        # 빌드본 자체 검증 (오프스크린 셀프테스트)
        Write-Host "== 셀프테스트 실행 =="
        $marker = Join-Path $env:TEMP "chess_brain_selftest_ok"
        Remove-Item $marker -ErrorAction SilentlyContinue
        $proc = Start-Process -FilePath $exe `
            -ArgumentList "--selftest" -Wait -PassThru
        $deadline = (Get-Date).AddSeconds(30)
        while (-not (Test-Path $marker) -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 500
        }
        $content = ""
        if (Test-Path $marker) {
            $content = (Get-Content $marker -Raw -ErrorAction SilentlyContinue)
        }
        # 마커 존재만이 아니라 drive=True 까지 확인한다.
        # 구글 라이브러리 번들이 깨지면 drive=False 로 찍히므로 빌드 단계에서 잡힌다.
        if (($proc.ExitCode -eq 0) -and ($content -match "drive=True")) {
            Write-Host "셀프테스트 통과 (drive=True)"
        } else {
            throw "셀프테스트 실패: 마커='$($content.Trim())' (exit=$($proc.ExitCode))"
        }
    } else {
        throw "$exe 가 생성되지 않음"
    }
}
finally {
    Remove-Item $keep -Recurse -Force -ErrorAction SilentlyContinue
}

Pop-Location
