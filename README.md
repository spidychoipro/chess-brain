<p align="center">
  <img src="https://raw.githubusercontent.com/spidychoipro/chess-brain/main/assets/chess-brain.svg" width="80" alt="chess-brain">
</p>

# chess-brain

![Python 3.15.2](https://img.shields.io/badge/Python-3.15.2-3776ab?logo=python&logoColor=white)
![tests 67 passing](https://img.shields.io/badge/tests-67%20passing-brightgreen)
![Stockfish sf_19 GPLv3](https://img.shields.io/badge/engine-Stockfish%20sf__19%20GPLv3-orange)
![release](https://img.shields.io/github/v/release/spidychoipro/chess-brain.svg)

chess-brain은 내가 둔 체스 대국에서 실수만 뽑아서 다시 풀게 하는 Windows 앱이다. Stockfish로 수마다 손실을 재고, 손실이 큰 수에 테마와 짧은 해설을 붙인다. 맞힌 문제는 며칠 뒤에, 자꾸 틀린 문제는 10분 뒤에 다시 나온다. 분석은 전부 로컬에서 돌고 로그인이나 결제는 없다.

[설치](#설치) · [사용법](#사용법) · [커리큘럼](#커리큘럼) · [데이터 가져오기](#데이터-가져오기) · [개발](#개발)

## 설치

### exe

[릴리스 페이지](https://github.com/spidychoipro/chess-brain/releases)에서 zip을 받아 아무 폴더에 풀고 `chess-brain.exe`를 실행하면 된다. 설치 프로그램은 없다.

zip에는 `chess-brain.exe`, `_internal\`, `engines\`가 들어 있다. `config\`와 `data\`는 들어 있지 않으므로, 이전에 쓰던 두 폴더를 새 폴더로 같이 옮기면 기록이 이어진다.

### 소스에서 실행

exe 없이 소스만 받아 돌릴 수도 있다. 관리자 권한은 필요 없다.

```powershell
git clone https://github.com/spidychoipro/chess-brain.git
cd chess-brain
py -3.15 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\fetch-stockfish.ps1
python main.py
```

`fetch-stockfish.ps1`은 공식 sf_19 실행 파일과 GPLv3 소스를 `engines\stockfish\`에 내려받는다. 직접 넣으려면 [Stockfish sf_19 릴리스](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19)에서 `stockfish-windows-x86-64-universal.zip`의 exe와 `Source code (zip)`의 `Copying.txt`, `src\`를 같은 폴더에 넣으면 된다.

첫 실행에서 `config\config.json`과 `data\app.db`가 생긴다. 엔진을 자동으로 못 찾으면 `config.json`에 경로를 적는다.

```json
{
  "stockfish": { "path": "C:\\path\\to\\stockfish.exe" },
  "local": { "pgn_folder": "C:\\path\\to\\my-pgns" }
}
```

엔진 경로가 비어 있어도 기보 트레이닝은 동작한다. 실수 분석만 실행되지 않는다.

## 사용법

1. 홈에서 `대국 가져오기`를 누른다. chess.com에서 받거나 로컬 PGN 폴더를 고른다.
2. `분석`을 누르면 엔진이 각 수의 손실을 잰다. 진행률이 표시되고 중단할 수 있다.
3. `훈련 커리큘럼`에서 `오늘의 추천 10문제`를 연다. 보드에서 기물을 클릭해서 수를 두고, 답을 모르겠으면 `모르겠음`을 누른다.

정답은 `모르겠음`을 누를 때만 공개된다. 그 전에 틀리면 빨간 표시만 뜨고 다시 시도한다.

실수에 붙는 해설은 이런 형식이다.

```text
수: Rg4
테마: 기물 걸림
설명: Rg4을 두면 상대가 Rxd4로 룩을 잡습니다. Rfd1가 정답입니다.
```

| 화면 | 내용 |
| --- | --- |
| 홈 | 오늘 복습할 항목, 가져오기·분석·복습 버튼 |
| 내 실수 | 실수 목록과 보드. 등급·소스 필터, 국면 다시 두기 |
| 기보 트레이닝 | 내가 둔 수 재현, 복습, 기보 읽기 4단계 |
| 훈련 커리큘럼 | 테마별 정답률과 재발, 추천 문제 |
| 기록/통계 | 최근 30일 성공률. 사람전과 봇전을 나눠서 표시 |
| 설정 | PGN 폴더, 엔진, 업데이트 확인, 백업, 로그 |

## 커리큘럼

테마는 엔진 결과에서 자동으로 분류된다. `메이트 놓침`, `메이트 당함`, `백 랭크`, `기물 걸림`, `잡을 수 놓침`, `포크·더블어택`, `핀·묶임`, `오프닝 판단`, `엔드게임`, `위치 판단`, `전술 미스`.

정답률이 낮은 테마에서 주로 문제를 뽑되 다른 테마도 섞는다. 테마를 직접 골라 집중 훈련할 수 있고, 최근 4주와 직전 4주에 새로 생긴 실수를 비교해서 재발 여부를 보여준다.

이미 4점 이상 지고 있거나 메이트당하기 직전인 국면은 카드에서 제외한다. 그런 국면은 무슨 수를 둬도 결과가 같다. 데이터는 삭제하지 않고 `excluded` 표시만 하며, `mistakes.skip_lost_positions`를 `false`로 바꾸면 다시 나온다. 옛 실수도 앱을 실행할 때 자동으로 정리된다.

## 데이터 가져오기

앱은 로컬 PGN 폴더를 읽는다. 폴더 아래에 `Human\`과 `Bot\`을 두면 사람전과 봇전으로 구분한다.

| 경로 | 필요한 것 |
| --- | --- |
| 로컬 폴더 | 폴더 지정만 하면 됨 |
| rclone | rclone 설치와 원격 경로. 앱은 인증 키를 갖지 않음 |
| 구글드라이브 | 공유 링크와 API 키 또는 `credentials.json` |

chess.com 자동 수집도 있다. 앱을 켜면 사람전·봇전 가리지 않고 아직 받지 않은 과거 게임을 훑는다. 게임 아카이브가 달 단위로 응답하므로 판 수가 요청 횟수에 영향을 주지 않는다. 이미 받은 게임은 `processed` 목록으로 걸러낸다. 실행 중에는 10분마다 최근 7일만 확인한다. 전체 수집 타임아웃은 3600초다.

수집 로그는 화면과 `data\chesscom-sync.log`에 남는다. 수집 도구가 없거나 네트워크가 막혀도 로컬 PGN 스캔은 그대로 진행된다.

인터넷은 업데이트 확인, chess.com 수집, 드라이브 연결에서만 쓴다. 전부 직접 요청할 때 연결하고, 평소 학습과 분석은 오프라인으로 된다.

## 기록 보관

앱을 실행할 때마다 `data\backups\`에 DB와 설정 사본을 남기고 최근 5개를 유지한다. 빌드할 때는 프로젝트의 `backups\build-<날짜>\`에 `config\`와 `data\`를 통째로 복사한다. 스키마가 바뀌어도 기존 DB를 초기화하지 않고 컬럼을 추가한다.

## 개발

```powershell
python -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

`build.ps1`은 설정과 DB를 백업한 뒤 빌드하고, 오프스크린 셀프테스트까지 돌린다. Python 3.15 환경에 패키지 설치가 막히면 기존 3.14 site-packages를 빌려 쓰는 처리가 들어 있다.

```text
main.py                 진입점 (--selftest)
core/                   chesscom 수집, 파싱, 엔진 분석, 커리큘럼, SQLite, 간격반복
ui/                     메인 창, 보드, 테마, 여섯 개 탭
assets/chess-brain.svg  로고
tests/                  unittest 67개
docs/learning-upgrade.md  학습 규칙 변경 기록
```

번들 엔진은 공식 Stockfish sf_19(GPLv3)이며 `engines\stockfish\`에 실행 파일과 `Copying.txt`, `src\`가 함께 들어간다.
