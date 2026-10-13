# chess-brain

체스닷컴에서 사람/봇이랑 둔 게임 PGN 을 (구글드라이브 또는 **로컬 폴더**)에서 읽어와서, **내 실수를 중심으로 복습**시키는 데스크탑 앱. 서브로 **기보(notation)만 보고 다음 수를 떠올리는 트레이닝**이 붙는다.

핵심은 "많이 풀기"가 아니라 **잊어버리기 직전에 다시 만나기**다. 그래서 복습 일정은 SM-2 경량 버전(간격 반복)으로 돌리고, 틀린 문제일수록 더 자주 나오게 가중치를 준다.

## 뭘 하는 앱인가

- 드라이브 **부모 폴더 하나**를 지정하면, 그 아래 `Bot` / `Human` 하위폴더를 보고 봇전/사람전을 자동으로 구분한다.
- PGN 은 드라이브에서 바로 읽기만 하고 로컬에 저장하지 않는다. DB 에는 **복습할 문제와 학습 기록만** 남긴다.
- **메인**: `내 실수(My Mistakes)` — Stockfish 로 내가 둔 수의 평가 손실을 재서 실수를 모으고, 그 실수를 간격 반복으로 복습한다.
- **서브**: `기보 시각화 트레이닝` — 앞부분 기보를 보여주고 **다음 수를 SAN 으로 직접 타이핑**하게 한다. 보드/자동완성은 의도적으로 없다.
- 엔진은 **옵션**이다. `stockfish.exe` 경로를 넣으면 실수 분석이 켜지고, 없으면 트레이닝만 돌아간다.

## 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
python main.py
```

처음 실행하면 `config/config.json` 과 `data/app.db` 가 자동 생성된다.

### 방법 1: 로컬 PGN 폴더 (무료·API 없음, 권장)

1. PGN 게임 파일을 로컬 폴더에 모은다. 아래에 `Bot` / `Human` 하위폴더를 두면 봇전/사람전이 자동 구분된다.
2. **설정** 탭 → **로컬 PGN 폴더**에서 폴더를 선택하고 **로컬 동기화**.
3. 실수 분석을 쓰려면 **설정** 에서 `stockfish.exe` 경로를 넣고, **내 실수** 탭에서 분석을 돌린다.

구글도, API도, 돈도 전혀 안 든다. 드라이브는 아래 방법 2로 옵션 지원한다.

### 방법 2: 구글드라이브 (선택·무료)

1. **설정** 탭에서 chess.com 아이디(내가 둔 수 판별용), 구글드라이브 부모 폴더 ID/URL 을 넣는다.
2. 구글 인증을 하려면 Google Cloud Console 에서 OAuth 클라이언트(데스크톱 앱)를 만들고 내려받은 json 을 `config/credentials.json` 으로 둔다. 그다음 **구글 인증** 버튼.
3. **드라이브 동기화** 를 누르면 `.pgn` 을 읽어 문제를 만든다.

드라이브 API 는 개인 읽기 용도로 무료다(결제 계정 불필요). 단, OAuth 클라이언트 만들기가 번거로우면 방법 1을 쓰면 된다.

## 구조

```
chess-brain/
├── core/
│   ├── config.py     # config.json 로드/저장
│   ├── db.py         # sqlite 스키마 + mistakes/problems/games 헬퍼
│   ├── sr.py         # SM-2 경량 (ease/interval/due_at)
│   ├── drive.py      # 구글드라이브 읽기전용 + Bot/Human 분류
│   ├── parser.py     # python-chess 로 내가 둔 수 추출
│   ├── engine.py     # Stockfish (선택)
│   └── pipeline.py   # 동기화 → 문제 생성 → 실수 분석
├── ui/
│   ├── main.py       # QMainWindow (사이드바 내비 + 헤더)
│   ├── theme.py      # 다크 테마 QSS + 디자인 토큰
│   ├── widgets.py    # SAN 입력 복습 패널/다이얼로그
│   ├── worker.py     # 동기화·분석용 QThread
│   └── tabs/         # home / mistakes / training / stats / settings
├── data/             # app.db (git 제외)
├── config/           # config.json, token.json (git 제외)
├── main.py
└── requirements.txt
```

## 복습 규칙 요약

- 정답 → 다음 간격으로 (1일 → 6일 → ×ease).
- 오답 → ease 를 조금 낮추고, **10분 뒤** 다시 만나게 한다. 그리고 같은 세션에서 곧바로 재출제.
- `origin='mistake'` (실수에서 파생된 문제)는 노테이션 연습에서 더 자주 뽑힌다.

## 메모

- `mistakes`(메인)와 `problems`(서브)는 통계를 **소스별로 분리**한다. 사람전 약점과 봇전 약점은 다르기 때문.
- 원본 PGN 을 로컬에 쌓지 않는 게 저장공간 절약의 핵심이다.
