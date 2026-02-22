"""
설정 관리 모듈
- 사용자 설정(아이디, 비밀번호, 카페 정보)을 저장/불러오기
- .env 파일 또는 런타임 입력 지원
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 기본 경로
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "crawler_config.json"
OUTPUT_DIR = BASE_DIR / "output"

# Naver 로그인 관련 URL
NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
NAVER_RSA_KEY_URL = "https://nid.naver.com/login/ext/keys.nhn"
NAVER_LOGOUT_URL = "https://nid.naver.com/nidlogin.logout"
NAVER_CAFE_BASE_URL = "https://cafe.naver.com"

# HTTP 헤더 (봇 탐지 우회)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://cafe.naver.com",
}

# 크롤링 설정
CRAWL_DELAY = 1.5          # 요청 간 딜레이(초) - 서버 부하 방지
MAX_RETRIES = 3            # 최대 재시도 횟수
REQUEST_TIMEOUT = 30       # 요청 타임아웃(초)
MAX_POSTS_PER_RUN = 100    # 1회 실행 시 최대 크롤링 게시글 수

# 스케줄 기본값
DEFAULT_SCHEDULE_TIME = "09:00"  # 매일 오전 9시 실행


def load_config() -> dict:
    """저장된 설정 불러오기"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config: dict) -> None:
    """설정 저장"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def ensure_output_dir() -> Path:
    """출력 디렉토리 생성"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR
