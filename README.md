# 네이버 카페 크롤러

네이버 카페의 게시글과 댓글을 수집하여 CSV 파일로 저장하는 프로그램입니다.

**두 가지 사용 방법:**
- **웹 인터페이스**: 브라우저에서 간편하게 사용
- **CLI (명령줄)**: 터미널에서 자동화 실행

## 설치

### 1. Python 3.8 이상 필요

```bash
python3 --version
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. Chrome 브라우저 필요

ChromeDriver는 자동으로 설치됩니다.

---

## 웹 인터페이스 (권장)

브라우저에서 간편하게 사용할 수 있는 웹 인터페이스를 제공합니다.

### 실행 방법

```bash
python web_app.py
```

### 접속

브라우저에서 다음 주소로 접속:

```
http://localhost:5000
```

### 웹 인터페이스 기능

| 기능 | 설명 |
|------|------|
| 크롤링 설정 | 카페 ID, 로그인 정보, 게시판 선택 |
| 실시간 로그 | 크롤링 진행 상황 실시간 확인 |
| 결과 확인 | 수집된 게시글/댓글 수 표시 |
| 파일 관리 | CSV 파일 다운로드 및 삭제 |

### 웹 사용 순서

1. `python web_app.py` 실행
2. 브라우저에서 `http://localhost:5000` 접속
3. 카페 ID, 네이버 아이디 입력
4. 게시판 이름/ID 또는 URL 입력
5. **크롤링 시작** 버튼 클릭
6. 새 브라우저 창에서 네이버 로그인
7. 로그인 완료 후 자동으로 크롤링 진행
8. 완료 시 CSV 다운로드

### 웹 화면 예시

```
+------------------------------------------+
|        네이버 카페 크롤러                   |
+------------------------------------------+
| 카페 ID: [iliveincan    ]                 |
| 네이버 아이디: [myid    ]                  |
| 비밀번호: [        ] (선택)                |
|                                          |
| [게시판 이름/ID] | [게시판 URL]            |
| [자유게시판     ]                          |
|                                          |
| 최대 게시글: [20]  최대 페이지: [1]         |
| [ ] 모든 게시글 수집                       |
|                                          |
|        [크롤링 시작]                       |
+------------------------------------------+
```

---

## CLI 사용법 (명령줄)

터미널에서 직접 실행하거나 자동화(cron)에 사용합니다.

```bash
python main.py --cafe <카페ID> --user <네이버아이디> [옵션]
```

### 필수 옵션

| 옵션 | 단축 | 설명 |
|------|------|------|
| `--cafe` | `-c` | 네이버 카페 ID (URL에서 확인) |
| `--user` | `-u` | 네이버 로그인 아이디 |

### 선택 옵션

| 옵션 | 단축 | 설명 | 기본값 |
|------|------|------|--------|
| `--password` | `-p` | 네이버 비밀번호 (미입력시 프롬프트) | - |
| `--board` | `-b` | 게시판 ID 또는 이름 | 대화형 선택 |
| `--board-url` | - | 게시판 URL 직접 입력 | - |
| `--manual-login` | - | 수동 로그인 모드 (권장) | 비활성 |
| `--all` | - | 모든 게시글 수집 (날짜 필터 해제) | 오늘만 |
| `--limit` | `-l` | 최대 게시글 수 | 20 |
| `--pages` | - | 조회할 페이지 수 | 1 |
| `--compact` | - | 컴팩트 CSV 형식 | 비활성 |
| `--headless` | - | 브라우저 숨김 모드 | 비활성 |
| `--verbose` | `-v` | 상세 로그 출력 | 비활성 |

---

## 사용 예시

### 1. 대화형 모드 (게시판 선택)

```bash
python main.py --cafe iliveincan --user myid --manual-login
```

실행 후 게시판 목록이 표시되고 번호로 선택합니다.

### 2. 게시판 이름으로 지정

```bash
python main.py --cafe iliveincan --user myid --manual-login --board "자유게시판"
```

### 3. 게시판 ID로 지정

```bash
python main.py --cafe iliveincan --user myid --manual-login --board 309
```

### 4. 게시판 URL로 직접 지정

```bash
python main.py --cafe iliveincan --user myid --manual-login \
  --board-url "https://cafe.naver.com/iliveincan?menuid=309"
```

### 5. 모든 게시글 수집 (오늘 필터 해제)

```bash
python main.py --cafe iliveincan --user myid --manual-login \
  --board 309 --all --limit 50 --pages 3
```

### 6. 자동화 실행 (비밀번호 포함)

```bash
python main.py --cafe iliveincan --user myid --password "mypassword" \
  --manual-login --board 309 --all --limit 10
```

---

## 게시판 URL 찾는 방법

1. 네이버 카페에 로그인
2. 원하는 게시판 클릭
3. 브라우저 주소창에서 URL 복사

**지원 URL 형식:**

```
https://cafe.naver.com/cafeid?menuid=123
https://cafe.naver.com/cafeid?iframe_url=/ArticleList.nhn?search.menuid=123
https://cafe.naver.com/ArticleList.nhn?search.clubid=xxx&search.menuid=123
```

---

## 로그인 모드

### 수동 로그인 모드 (권장)

```bash
python main.py --cafe iliveincan --user myid --manual-login
```

- 브라우저가 열리면 직접 로그인
- 캡차 우회 가능
- 2단계 인증 지원

### 자동 로그인 모드

```bash
python main.py --cafe iliveincan --user myid --password "mypassword"
```

- 자동으로 아이디/비밀번호 입력
- 캡차 감지 시 실패할 수 있음

---

## 출력 파일

### 저장 위치

```
output/카페ID_게시판명_날짜.csv
```

예: `output/iliveincan_자유게시판_20260224.csv`

### CSV 형식 (기본)

게시글당 댓글 수만큼 행이 생성됩니다.

| 컬럼 | 설명 |
|------|------|
| post_id | 게시글 ID |
| title | 게시글 제목 |
| author | 게시글 작성자 |
| date | 게시글 작성일 |
| views | 조회수 |
| content | 게시글 본문 |
| comment_author | 댓글 작성자 |
| comment_content | 댓글 내용 |
| comment_date | 댓글 작성일 |
| url | 게시글 URL |

### CSV 형식 (컴팩트)

`--compact` 옵션 사용 시 게시글당 1행, 댓글은 JSON으로 저장됩니다.

---

## 자동 실행 (cron)

### 1. 환경 변수 설정

`.env` 파일 생성:

```bash
cp .env.example .env
```

`.env` 파일 편집:

```
NAVER_CAFE_ID=iliveincan
NAVER_USER_ID=myid
NAVER_PASSWORD=mypassword
BOARD_ID=309
```

### 2. cron 등록

```bash
crontab -e
```

매일 오전 9시 실행:

```
0 9 * * * /path/to/localk_contents_cafe/cron_runner.sh >> /path/to/logs/cron.log 2>&1
```

---

## 문제 해결

### 1. 로그인 실패

- `--manual-login` 옵션 사용
- 캡차가 나타나면 직접 입력

### 2. 게시판 목록이 비어 있음

- 카페 가입 여부 확인
- 로그인 상태 확인

### 3. 게시글이 수집되지 않음

- `--all` 옵션으로 날짜 필터 해제
- `--limit`, `--pages` 값 증가

### 4. ChromeDriver 오류

```bash
pip install --upgrade webdriver-manager
```

---

## 로그 파일

```
logs/crawler_YYYYMMDD.log
```

상세 로그 출력:

```bash
python main.py --cafe iliveincan --user myid --manual-login -v
```

---

## 프로젝트 구조

```
localk_contents_cafe/
├── main.py                 # CLI 진입점
├── web_app.py              # 웹 서버 (Flask)
├── templates/
│   └── index.html          # 웹 UI
├── config/
│   └── settings.py         # 설정
├── src/
│   ├── auth/
│   │   └── naver_login.py  # 로그인
│   ├── crawler/
│   │   ├── cafe_crawler.py # 메인 크롤러
│   │   ├── board_parser.py # 게시판 파싱
│   │   └── post_parser.py  # 게시글 파싱
│   ├── storage/
│   │   └── csv_handler.py  # CSV 저장
│   └── utils/
│       ├── browser.py      # 브라우저 설정
│       ├── date_utils.py   # 날짜 처리
│       └── iframe_handler.py # iframe 처리
├── output/                 # CSV 출력
├── logs/                   # 로그
├── requirements.txt
├── cron_runner.sh          # cron 스크립트
└── .env.example            # 환경변수 예시
```

---

## 라이선스

이 프로그램은 개인 사용 목적으로 제작되었습니다.
네이버 서비스 이용약관을 준수하여 사용하시기 바랍니다.
