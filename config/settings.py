"""
네이버 카페 크롤러 설정
"""
import os
import json
from pathlib import Path

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).resolve().parent.parent

# 네이버 URL
NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
NAVER_CAFE_BASE_URL = "https://cafe.naver.com"

# 출력 경로
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
CONFIG_DIR = BASE_DIR / "config"

# 타임아웃 설정 (초)
DEFAULT_TIMEOUT = 10
PAGE_LOAD_WAIT = 3
ELEMENT_WAIT = 5

# 요청 간격 (초) - 과도한 요청 방지
REQUEST_DELAY = 1.5

# User-Agent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 수집 제외 키워드 설정 파일
EXCLUDE_KEYWORDS_FILE = CONFIG_DIR / "exclude_keywords.json"

# 출력 디렉토리 생성
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)


class ExcludeKeywordsManager:
    """수집 제외 키워드 관리 클래스"""

    def __init__(self, filepath: Path = None):
        self.filepath = filepath or EXCLUDE_KEYWORDS_FILE
        self._keywords = []
        self._load()

    def _load(self):
        """키워드 목록 로드"""
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._keywords = data.get('keywords', [])
            except Exception:
                self._keywords = []
        else:
            self._keywords = []
            self._save()

    def _save(self):
        """키워드 목록 저장"""
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump({'keywords': self._keywords}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"키워드 저장 실패: {e}")

    def get_keywords(self) -> list:
        """현재 제외 키워드 목록 반환"""
        return self._keywords.copy()

    def add_keyword(self, keyword: str) -> bool:
        """키워드 추가"""
        keyword = keyword.strip()
        if keyword and keyword not in self._keywords:
            self._keywords.append(keyword)
            self._save()
            return True
        return False

    def remove_keyword(self, keyword: str) -> bool:
        """키워드 제거"""
        keyword = keyword.strip()
        if keyword in self._keywords:
            self._keywords.remove(keyword)
            self._save()
            return True
        return False

    def set_keywords(self, keywords: list) -> None:
        """키워드 목록 전체 설정"""
        self._keywords = [k.strip() for k in keywords if k.strip()]
        self._save()

    def clear_keywords(self) -> None:
        """모든 키워드 삭제"""
        self._keywords = []
        self._save()

    def contains_excluded_keyword(self, text: str) -> bool:
        """
        텍스트에 제외 키워드가 포함되어 있는지 확인

        Args:
            text: 확인할 텍스트

        Returns:
            제외 키워드 포함 여부
        """
        if not text or not self._keywords:
            return False
        text_lower = text.lower()
        for keyword in self._keywords:
            if keyword.lower() in text_lower:
                return True
        return False


# 전역 인스턴스
exclude_keywords_manager = ExcludeKeywordsManager()
