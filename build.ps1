# chess-brain 실행 파일 빌드 (PyInstaller, onefile + windowed)
# 결과: dist\chess-brain.exe  → 더블클릭으로 실행
$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$py = "C:\Users\swpar\AppData\Local\Programs\Python\Python314\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "== PyInstaller 설치 =="
& $py -m pip install --upgrade pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pyinstaller 설치 실패" }

Write-Host "== 빌드 =="
& $py -m PyInstaller --noconfirm --clean --onefile --windowed --name chess-brain `
    --hidden-import googleapiclient `
    --hidden-import googleapiclient.discovery `
    --hidden-import googleapiclient.http `
    --hidden-import google_auth_oauthlib `
    --hidden-import google_auth_oauthlib.flow `
    --hidden-import google.auth `
    --hidden-import google.auth.transport `
    --hidden-import google.auth.transport.requests `
    main.py
if ($LASTEXITCODE -ne 0) { throw "빌드 실패" }

if (Test-Path "dist\chess-brain.exe") {
    Write-Host "== 완료: $((Get-Item 'dist\chess-brain.exe').FullName) =="
    # 빌드본 자체 검증 (오프스creen 셀프테스트)
    Write-Host "== 셀프테스트 실행 =="
    $marker = Join-Path $env:TEMP "chess_brain_selftest_ok"
    Remove-Item $marker -ErrorAction SilentlyContinue
    $proc = Start-Process -FilePath "dist\chess-brain.exe" `
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
    throw "dist\chess-brain.exe 가 생성되지 않음"
}

Pop-Location