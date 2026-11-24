<p align="center">
  <img src="https://raw.githubusercontent.com/spidychoipro/chess-brain/main/assets/chess-brain.svg" width="92" alt="chess-brain">
</p>

<h1 align="center">chess-brain</h1>

<p align="center"><em>내 실수만 다시 푸는 체스 훈련 앱</em></p>

<p align="center">
  <img alt="Python 3.15.2" src="https://img.shields.io/badge/Python-3.15.2-3776ab?logo=python&logoColor=white">
  <img alt="tests 67 passing" src="https://img.shields.io/badge/tests-67%20passing-brightgreen">
  <img alt="Stockfish sf_19 GPLv3" src="https://img.shields.io/badge/engine-Stockfish%20sf__19%20GPLv3-orange">
  <img alt="release" src="https://img.shields.io/github/v/release/spidychoipro/chess-brain.svg">
</p>

---

## 왜 chess-brain인가?

대국은 쌓이는데 같은 실수가 계속 나온다. 기보를 처음부터 다시 보는 건 오래 걸리고, 뭘 연습해야 할지도 잡히지 않는다. chess-brain은 내 대국에서 **손해 본 수만** 뽑아서 이름을 붙이고, 잊기 직전에 다시 풀게 한다.

- **실수만 남긴다** — Stockfish가 수마다 손실을 재고, 기준을 넘는 수만 모은다.
- **왜 틀렸는지 설명한다** — 메이트 놓침, 백 랭크, 기물 걸림 같은 테마를 붙이고 사람 말로 해설을 달아준다.
- **약한 데서 문제를 낸다** — 정답률이 낮은 테마에서 오늘의 10문제를 골라준다.
- **잊기 직전에 다시 만난다** — 맞히면 간격을 늘리고, 자꾸 틀리면 10분 뒤에 다시 내놓는다.
- **전부 로컬에서 돌아간다** — 기록은 SQLite, 분석은 번들 Stockfish. 로그인도 결제도 없다.

## 시작하기

### exe로 쓰기

[릴리스 페이지](https://github.com/spidychoipro/chess-brain/releases)에서 zip을 받아 아무 폴더에 풀고 `chess-brain.exe`를 더블클릭하면 끝이다. 설치 프로그램은 없다.

zip 안에는 `chess-brain.exe`, `_internal\`, `engines\`가 들어 있다. 내 기록인 `config\`와 `data\`는 안 들어가니까, 쓰던 폴더에서 두 폴더를 같이 옮기면 그대로 이어진다.

### 소스에서 직접 쓰기

exe 없이 소스만 받아 돌리는 방법이다. 관리자 권한도 필요 없다.

```powershell
git clone https://github.com/spidychoipro/chess-brain.git
cd chess-brain
py -3.15 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File .\fetch-stockfish.ps1
python main.py
```

`fetch-stockfish.ps1`은 공식 sf_19 바이너리와 GPLv3 소스를 `engines\stockfish\`에 넣는다. 직접 넣으려면 [Stockfish sf_19 릴리스](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19)에서 `stockfish-windows-x86-64-universal.zip` 안의 exe를 `engines\stockfish\`에, `Source code (zip)`의 `Copying.txt`와 `src\`를 같은 폴더에 넣으면 된다.

처음 실행하면 `config\config.json`과 `data\app.db`가 저절로 생긴다. 설정에서 PGN 폴더만 지정하면 쓸 수 있다. 엔진을 못 찾으면 `config.json`에 경로를 적는다.

```json
{
  "stockfish": { "path": "C:\\path\\to\\stockfish.exe" },
  "local": { "pgn_folder": "C:\\path\\to\\my-pgns" }
}
```

나중에 업데이트할 땐 소스만 새 것으로 갈아끼우면 된다. `config\`와 `data\`는 그대로 두면 된다.

## 쓰는 법

1. 홈에서 **대국 가져오기**를 누른다. chess.com에서 받아도 되고 PGN 파일이 든 폴더를 골라도 된다. 폴더 아래에 `Human\`과 `Bot\`을 두면 사람전과 봇전으로 나뉜다.
2. **분석**을 누르면 엔진이 손실을 재고 실수를 모은다. 진행률이 나오고 도중에 멈출 수도 있다.
3. 왼쪽에서 **훈련 커리큘럼 → 오늘의 추천 10문제**를 연다. 보드에서 기물을 클릭해서 수를 두고, 모르겠으면 **모르겠음**을 눌러 정답을 본다.

다음 날엔 복습할 문제가 알아서 떠 있다.

## 화면

| 화면 | 하는 일 |
| --- | --- |
| 홈 | 오늘 할 일, 요약, 가져오기·분석·복습 버튼 |
| 내 실수 | 실수 목록 + 보드. 등급·소스 필터, 국면 다시 두기 |
| 기보 트레이닝 | 내가 둔 수 재현, 복습, 기보 읽기 4단계 |
| 훈련 커리큘럼 | 테마별 약점, 추천 문제, 재발 추적 |
| 기록/통계 | 최근 정답률과 자주 틀리는 패턴. 사람전/봇전 분리 |
| 설정 | 폴더, 엔진, 백업, 업데이트 확인 |

기보를 못 읽어도 된다. 수를 타이핑하는 게 아니라 보드에서 기물을 누르면 된다. 틀리면 빨간 표시가 뜨고, 정답은 **모르겠음**을 누를 때만 공개된다.

## 훈련 커리큘럼

테마는 엔진 결과에서 자동으로 붙는다. 메이트 놓침, 메이트 당함, 백 랭크, 기물 걸림, 잡을 수 놓침, 포크·더블어택, 핀·묶임, 오프닝 판단, 엔드게임, 위치 판단, 전술 미스.

해설은 이런 식으로 붙는다.

> `Rg4`을 두면 상대가 `Rxd4`로 룩을 잡습니다. `Rfd1`가 정답입니다.

커리큘럼 화면에서 테마별 실수 수, 복습 예정, 정답률, 최근 4주 재발을 본다. 테마를 골라 집중 훈련도 할 수 있다.

이미 4점 이상 지고 있거나 메이트당하기 직전인 국면은 카드에서 빠진다. 거기선 무슨 수를 둬도 결과가 같아서 외울 게 없다. DB에는 그대로 남아 있고, `mistakes.skip_lost_positions`를 `false`로 바꾸면 다시 나온다.

## 대국 가져오기

앱은 결국 로컬 폴더를 읽는다.

| 경로 | 필요한 것 |
| --- | --- |
| 로컬 PGN 폴더 | 폴더 지정만 하면 됨 |
| rclone | rclone 설치 + 원격 경로. 앱은 키를 갖지 않음 |
| 구글드라이브 | 공유 링크 + API 키 또는 credentials.json |

chess.com 자동 수집도 켜져 있다. 앱을 켜면 사람전·봇전 가리지 않고 아직 안 받은 과거 게임을 전부 훑는다. 30판이든 300판이든 달 단위로 몰아서 받으니 판 수가 요청 횟수에 영향을 주지 않는다. 실행 중에는 10분마다 최근 7일만 가볍게 확인한다. 수집 로그는 화면과 `data\chesscom-sync.log`에 남고, 설정에서 자동 수집을 끌 수 있다.

평소 학습과 분석은 오프라인으로 된다. 인터넷을 쓰는 건 업데이트 확인, chess.com 수집, 드라이브 연결 정도이고 전부 직접 누를 때만 연결한다. 업데이트 확인은 GitHub 태그를 조회해서 새 버전이 있으면 릴리스 페이지를 알려준다.

## 기록 보관

앱을 켤 때마다 `data\backups\`에 DB와 설정 사본을 남기고 최근 5개를 유지한다. 빌드할 때는 프로젝트의 `backups\build-<날짜>\`에 `config\`와 `data\`를 통째로 복사해둔다. 스키마가 바뀌어도 기존 DB는 초기화하지 않고 컬럼을 추가한다.

## 코드 구조

```
main.py                 진입점 (--selftest)
core/                   chesscom 수집, 파싱, 엔진 분석, 커리큘럼, SQLite, 간격반복
ui/                     메인 창, 보드, 테마, 여섯 개 탭
assets/chess-brain.svg  로고
tests/                  unittest 67개
docs/learning-upgrade.md 학습 규칙 변경 기록
```

엔진은 공식 Stockfish sf_19(GPLv3)를 번들한다. `engines\stockfish\`에 exe와 `Copying.txt`, `src\`가 함께 들어간다. 소스 빌드는 `fetch-stockfish.ps1`로 엔진을 받은 뒤 `build.ps1`을 돌리면 되고, 빌드는 설정과 DB를 백업한 뒤 되돌린다. 테스트는 `python -m unittest discover -s tests -v`로 돌린다.
