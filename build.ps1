# chess-brain 실행 파일 빌드 (PyInstaller, onedir + windowed)
# onedir = 실행 시 매번 74MB 를 임시폴더에 풀지 않아서 시작이 빠르다.
# 결과: dist\chess-brain\chess-brain.exe  → 더블클릭으로 실행
#
# 주의: PyInstaller --noconfirm 은 출력 폴더(dist\chess-brain)를 통째로 지운다.
#   그 안에 사용자 설정(config\config.json, token.json ...)과 학습 DB(data\app.db)가
#   같이 들어 있다. 빌드 전에 backups\build-<시각> 으로 복사해두고, 성공하든
#   실패하든 그 사본을 남기고 되돌린다. 임시폴더는 쓰지 않는다(청소되면 끝).
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$py = "C:\Users\swpar\AppData\Local\Programs\Python\Python314\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

$out = "dist\chess-brain"
$backupRoot = Join-Path (Get-Location).Path "backups"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
$keep = Join-Path $backupRoot ("build-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Force -Path $keep | Out-Null

# -- 빌드 전: 사용자 설정/DB 를 영구 백업 ------------------------------------
$saved = @()
foreach ($sub in @("config", "data")) {
    $src = Join-Path $out $sub
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $keep $sub) -Recurse -Force
        $saved += $sub
    }
}
if ($saved.Count -gt 0) {
    Write-Host "== 설정/DB 백업: $keep =="
}

Write-Host "== PyInstaller 설치 =="
& $py -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pyinstaller 설치 실패" }

$restore = {
    foreach ($sub in @("config", "data")) {
        $bk = Join-Path $keep $sub
        if (Test-Path $bk) {
            $dst = Join-Path $out $sub
            New-Item -ItemType Directory -Force -Path $dst | Out-Null
            Copy-Item (Join-Path $bk "*") $dst -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

$verified = $false
try {
    Write-Host "== 빌드 =="
    # 주의: unittest 는 절대 제외하지 말 것.
    #   googleapiclient -> httplib2 -> pyparsing -> pyparsing.testing 이 import 시점에
    #   unittest 를 끌어온다. 빼면 드라이브/로컬 동기화가 "No module named 'unittest'" 로 깨진다.
    & $py -m PyInstaller --noconfirm --clean chess-brain.spec
    if ($LASTEXITCODE -ne 0) { throw "빌드 실패" }

    # -- 빌드 후: 포터블 Stockfish 를 앱 폴더에 넣는다 ------------------------
    # PyInstaller 가 dist\chess-brain 을 통째로 지우므로 빌드 뒤에 복사해야 한다.
    # zip 에 같이 들어가서 새 사용자도 설정 없이 실수 분석을 바로 쓸 수 있다.
    $engineSrc = "engines\stockfish"
    if (Test-Path $engineSrc) {
        $engineDst = Join-Path $out "engines\stockfish"
        New-Item -ItemType Directory -Force -Path $engineDst | Out-Null
        Copy-Item (Join-Path $engineSrc "*") $engineDst -Recurse -Force
        Write-Host "== 포터블 Stockfish 동봉 =="
    } else {
        Write-Host "== engines\stockfish 없음 — 내려받으려면 fetch-stockfish.ps1 실행 =="
    }

    # -- 빌드 후: 백업한 설정/DB 복원 (셀프테스트보다 먼저) -------------------
    & $restore
    foreach ($sub in $saved) {
        if (-not (Test-Path (Join-Path $out $sub))) {
            throw "복원 확인 실패: $sub"
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
    $verified = $true
}
finally {
    # 빌드 실패든 셀프테스트 실패든 상관없이 마지막에 한 번 더 되돌린다.
    # 백업 폴더는 지우지 않는다. 사고 나면 여기서 꺼내 쓰면 된다.
    if (-not $verified) {
        & $restore
        if ($saved.Count -gt 0) {
            Write-Host "== 실패 — 백업에서 복구함: $keep =="
        }
    }
    # 최근 5개 빌드 백업만 남긴다.
    Get-ChildItem $backupRoot -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        Select-Object -Skip 5 |
        ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
}

Pop-Location
