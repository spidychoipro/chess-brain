<img src="https://raw.githubusercontent.com/spidychoipro/chess-brain/main/assets/chess-brain.svg" width="84" alt="chess-brain">

# chess-brain

![Python 3.15.2](https://img.shields.io/badge/Python-3.15.2-3776ab?logo=python&logoColor=white)
![tests 67 passing](https://img.shields.io/badge/tests-67%20passing-brightgreen)
![Stockfish GPLv3](https://img.shields.io/badge/engine-Stockfish%20sf__19%20GPLv3-orange)

내가 둔 체스 대국에서 **실수만 골라서 다시 풀게 해주는** 앱입니다.

기보를 몰라도 괜찮습니다. 보드에서 기물을 클릭하면 수가 두어집니다. 틀린 이유도 사람 말로 알려줍니다. 돈도 안 들고, 인터넷 없이도 돌아갑니다.

---

## 이걸로 뭐 하나요?

- 내 대국을 읽어서 "여기서 손해 봤다"는 수만 골라줍니다.
- 그 수에 메이트 놓침, 백 랭크, 기물 걸림 같은 이름을 붙이고 왜 틀렸는지 설명합니다.
- 약한 부분에서 문제를 골라줍니다. 맞히면 며칠 뒤에, 자꾸 틀리면 더 자주 다시 나옵니다.

외우려고 푸는 게 아니라, **같은 실수를 안 하게 되는 쪽**에 목적이 있습니다.

## 하루에 이렇게 쓰면 돼요

1. 홈에서 **대국 가져오기**를 누릅니다. chess.com 계정을 연결해도 되고, PGN 파일이 든 폴더를 골라도 됩니다.
2. **분석**을 누르면 엔진이 실수를 뽑아줍니다. 잠깐 걸립니다.
3. 왼쪽에서 **훈련 커리큘럼**을 열고 **오늘의 추천 10문제**를 누릅니다.

끝입니다. 다음 날엔 복습할 게 알아서 떠 있습니다.

## 설치

### 제일 쉬운 방법

[릴리스 페이지](https://github.com/spidychoipro/chess-brain/releases)에서 zip을 받아서 아무 폴더에 풀고 `chess-brain.exe`를 더블클릭하면 됩니다. 설치 프로그램은 없습니다.

zip 안에는 exe와 엔진이 들어 있습니다. 내 기록은 zip에 없으니까, 예전에 쓰던 `config`와 `data` 폴더를 새 폴더로 같이 옮기면 그대로 이어집니다.

<details>
<summary>소스에서 직접 설치하고 싶다면</summary>

관리자 권한도, exe도 필요 없습니다.

**1. 소스 받기**

GitHub에서 **Code → Download ZIP** 을 눌러 풀거나 `git clone https://github.com/spidychoipro/chess-brain.git` 을 실행합니다.

**2. 파이썬 준비**

Python 3.10 이상을 설치한 뒤, 그 폴더에서 이렇게 칩니다.

```powershell
py -3.15 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**3. 엔진 넣기**

[Stockfish sf_19](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19) 페이지에서 `stockfish-windows-x86-64-universal.zip`을 받아, 안의 exe를 `engines\stockfish\`에 넣습니다. 같은 페이지의 `Source code (zip)`도 받아서 `Copying.txt`와 `src\`를 같이 넣어주면 더 좋습니다(GPLv3 때문).

귀찮으면 `powershell -ExecutionPolicy Bypass -File .\fetch-stockfish.ps1` 한 줄로 자동으로 됩니다.

**4. 실행**

```powershell
python main.py
```

처음 켜면 `config\config.json`과 `data\app.db`가 저절로 생깁니다. 설정에서 PGN 폴더만 지정하면 끝입니다. 엔진은 위 경로를 자동으로 찾고, 못 찾으면 `config.json`의 `stockfish.path`에 exe 경로를 적으면 됩니다.

나중에 업데이트할 땐 소스만 새 것으로 바꾸면 됩니다. `config`와 `data`는 그대로 두세요.

</details>

## 화면은 이렇게 생겼습니다

- **홈** — 오늘 할 일과 요약. 여기서 대국 가져오기, 분석, 복습을 바로 시작합니다.
- **내 실수** — 실수 목록과 보드가 나란히 있습니다. 행을 누르면 그 국면이 떠서 직접 다시 둘 수 있습니다.
- **기보 트레이닝** — 내가 둔 수 재현하기, 복습하기, 기보 읽는 법 처음부터 배우기.
- **훈련 커리큘럼** — 테마별로 어디가 약한지 보고, 거기서 문제를 골라풉니다.
- **기록/통계** — 최근 정답률과 자주 틀리는 패턴. 사람전과 봇전을 나눠서 봅니다.
- **설정** — 폴더, 엔진, 백업, 업데이트 확인.

## 자주 묻는 것

**기보를 하나도 모르는데 쓸 수 있나요?**
네. 수를 타이핑하는 게 아니라 보드에서 기물을 누르면 됩니다. "기보 읽기 배우기" 모드도 따로 있습니다.

**인터넷이 꼭 필요한가요?**
아니요. 평소엔 전부 오프라인으로 됩니다. 인터넷 쓰는 건 업데이트 확인, chess.com에서 대국 받아오기, 드라이브 연결 정도이고 전부 직접 누를 때만 연결합니다.

**봇 게임도 다 가져오나요?**
네. 사람전이든 봇전이든 몇 판을 두든 과거 전부 받아옵니다.

**이미 크게 지고 있는 국면도 나오나요?**
아니요. 거기선 무슨 수를 둬도 결과가 같아서 외울 게 없습니다. 그런 카드는 빼고, DB에는 그대로 남겨둡니다.

**기록이 사라질까 봐 걱정됩니다.**
앱을 켤 때마다 `data\backups\`에 사본을 남깁니다. 설정의 **백업 폴더 열기**에서 바로 볼 수 있습니다. 빌드할 때도 프로젝트 `backups\`에 통째로 복사해둡니다.

**돈은 안 드나요?**
안 듭니다. 엔진도 공식 Stockfish를 같이 넣어둔 거라 과금 API가 없습니다. 유료 서비스 주소가 코드에 들어오면 테스트가 먼저 실패하도록 막아뒀습니다.

<details>
<summary>개발자용 메모</summary>

소스 실행은 `python main.py`, 테스트는 `python -m unittest discover -s tests -v` (67개 통과)입니다. exe로 만들려면 `fetch-stockfish.ps1`로 엔진을 받은 뒤 `build.ps1`을 돌리면 됩니다. 빌드는 설정과 DB를 백업해두고 되돌립니다.

코드는 `core/`(수집·분석·저장·커리큘럼), `ui/`(화면), `tests/`로 나뉘어 있습니다.

</details>
