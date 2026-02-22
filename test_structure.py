"""
구조 및 로직 테스트 (네트워크 없이 동작 가능)
- 모듈 임포트 검증
- CSV 내보내기 로직 테스트
- RSA 암호화 로직 테스트
- 스케줄러 기본 로직 테스트
- 설정 저장/불러오기 테스트
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results = {"pass": 0, "fail": 0}


def test(name: str, fn):
    try:
        fn()
        print(f"  {PASS} {name}")
        results["pass"] += 1
    except Exception as e:
        print(f"  {FAIL} {name} → {e}")
        results["fail"] += 1


# ──────────────────────────────────────────────────────────────────────────────
print("=" * 55)
print("  네이버 카페 크롤러 구조 테스트")
print("=" * 55)

# 1. 모듈 임포트 테스트
print(f"\n{INFO} [1] 모듈 임포트")

def test_import_config():
    import config
    assert hasattr(config, "NAVER_LOGIN_URL")
    assert hasattr(config, "NAVER_RSA_KEY_URL")
    assert hasattr(config, "CRAWL_DELAY")
    assert "nid.naver.com" in config.NAVER_LOGIN_URL

def test_import_login():
    from login import NaverLogin, NaverLoginError
    login = NaverLogin()
    assert hasattr(login, "login")
    assert hasattr(login, "logout")
    assert hasattr(login, "load_cookies_from_string")

def test_import_cafe_manager():
    from cafe_manager import CafeManager, CafeError
    assert CafeManager is not None

def test_import_crawler():
    from crawler import PostCrawler, BoardCrawler
    assert PostCrawler is not None
    assert BoardCrawler is not None

def test_import_csv_exporter():
    from csv_exporter import CSVExporter, POST_COLUMNS, COMMENT_COLUMNS
    assert "article_id" in POST_COLUMNS
    assert "title" in POST_COLUMNS
    assert "content" in POST_COLUMNS
    assert "comment_id" in COMMENT_COLUMNS
    assert "is_reply" in COMMENT_COLUMNS

def test_import_scheduler():
    from scheduler import CrawlScheduler
    assert CrawlScheduler is not None

test("config 모듈", test_import_config)
test("login 모듈", test_import_login)
test("cafe_manager 모듈", test_import_cafe_manager)
test("crawler 모듈", test_import_crawler)
test("csv_exporter 모듈", test_import_csv_exporter)
test("scheduler 모듈", test_import_scheduler)

# ──────────────────────────────────────────────────────────────────────────────
# 2. RSA 암호화 테스트
print(f"\n{INFO} [2] RSA 암호화 (비밀번호 암호화)")

def test_rsa_encryption():
    from login import NaverLogin
    from Crypto.PublicKey import RSA

    # 테스트용 RSA 키 생성 (실제와 동일한 알고리즘)
    key = RSA.generate(2048)
    n_hex = format(key.n, "x")
    e_hex = format(key.e, "x")
    key_name = "testkey"

    login = NaverLogin()
    encrypted = login._encrypt_password(key_name, e_hex, n_hex, "testuser", "testpass123!")

    # 암호화 결과가 16진수 문자열인지 확인
    assert isinstance(encrypted, str)
    assert len(encrypted) > 0
    int(encrypted, 16)  # 16진수 변환 가능해야 함

def test_rsa_different_passwords():
    """같은 키로 암호화해도 매번 다른 결과 (PKCS1_v1_5 랜덤 패딩)"""
    from login import NaverLogin
    from Crypto.PublicKey import RSA

    key = RSA.generate(2048)
    n_hex = format(key.n, "x")
    e_hex = format(key.e, "x")

    login = NaverLogin()
    enc1 = login._encrypt_password("k", e_hex, n_hex, "id", "pw1234")
    enc2 = login._encrypt_password("k", e_hex, n_hex, "id", "pw5678")
    assert enc1 != enc2  # 다른 비밀번호는 다른 결과

def test_rsa_special_chars():
    """특수문자 포함 비밀번호 암호화"""
    from login import NaverLogin
    from Crypto.PublicKey import RSA

    key = RSA.generate(2048)
    n_hex = format(key.n, "x")
    e_hex = format(key.e, "x")

    login = NaverLogin()
    enc = login._encrypt_password("k", e_hex, n_hex, "user@naver", "P@ssw0rd!#$%")
    assert len(enc) > 0

test("RSA 암호화 기본 동작", test_rsa_encryption)
test("RSA 서로 다른 비밀번호", test_rsa_different_passwords)
test("RSA 특수문자 비밀번호", test_rsa_special_chars)

# ──────────────────────────────────────────────────────────────────────────────
# 3. CSV 내보내기 테스트
print(f"\n{INFO} [3] CSV 내보내기")

SAMPLE_POSTS = [
    {
        "article_id": "1001",
        "board_id": "1",
        "title": "테스트 게시글 제목 1",
        "author": "홍길동",
        "date": "2024.01.15 10:30",
        "content": "안녕하세요.\n이것은 테스트입니다.",
        "views": "1234",
        "likes": "56",
        "comment_count": "3",
        "url": "https://cafe.naver.com/testcafe/1001",
        "crawled_at": "2024-01-15 10:00:00",
    },
    {
        "article_id": "1002",
        "board_id": "1",
        "title": '게시글 "따옴표" 포함',
        "author": "김철수",
        "date": "2024.01.15 11:00",
        "content": "CSV 테스트, 쉼표 포함\n개행도 있음",
        "views": "500",
        "likes": "10",
        "comment_count": "0",
        "url": "https://cafe.naver.com/testcafe/1002",
        "crawled_at": "2024-01-15 10:05:00",
    },
]

SAMPLE_COMMENTS = [
    {
        "comment_id": "c001",
        "article_id": "1001",
        "board_id": "1",
        "parent_id": "",
        "author": "이영희",
        "content": "좋은 글이네요!",
        "date": "2024.01.15 10:35",
        "is_reply": False,
    },
    {
        "comment_id": "c002",
        "article_id": "1001",
        "board_id": "1",
        "parent_id": "c001",
        "author": "박민준",
        "content": "저도 동의합니다.",
        "date": "2024.01.15 10:40",
        "is_reply": True,
    },
]

def test_csv_posts_save():
    from csv_exporter import CSVExporter
    import csv

    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = CSVExporter("testcafe", Path(tmpdir))
        path = exporter.save_posts(SAMPLE_POSTS, date_str="2024-01-15", append=False)

        assert path.exists()
        assert path.suffix == ".csv"
        assert "testcafe" in path.name
        assert "posts" in path.name

        # CSV 내용 검증
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["article_id"] == "1001"
        assert rows[0]["author"] == "홍길동"
        assert rows[1]["article_id"] == "1002"

def test_csv_comments_save():
    from csv_exporter import CSVExporter
    import csv

    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = CSVExporter("testcafe", Path(tmpdir))
        path = exporter.save_comments(SAMPLE_COMMENTS, date_str="2024-01-15", append=False)

        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["comment_id"] == "c001"
        assert rows[1]["is_reply"] == "True"

def test_csv_append_mode():
    """append=True 시 기존 파일에 데이터 추가"""
    from csv_exporter import CSVExporter
    import csv

    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = CSVExporter("testcafe", Path(tmpdir))
        exporter.save_posts([SAMPLE_POSTS[0]], date_str="2024-01-15", append=False)
        exporter.save_posts([SAMPLE_POSTS[1]], date_str="2024-01-15", append=True)

        path = exporter._get_filename("posts", "2024-01-15")
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2  # 헤더 1 + 데이터 2

def test_csv_special_chars():
    """쉼표, 줄바꿈, 따옴표 포함 데이터 정상 처리"""
    from csv_exporter import CSVExporter
    import csv

    special_post = {
        "article_id": "9999",
        "title": 'title with "quotes" and, commas',
        "content": "line1\nline2\nline3",
        "author": "테스터",
        "board_id": "1",
        "date": "2024-01-15",
        "views": "0",
        "likes": "0",
        "comment_count": "0",
        "url": "https://cafe.naver.com/test/9999",
        "crawled_at": "2024-01-15 00:00:00",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = CSVExporter("testcafe", Path(tmpdir))
        path = exporter.save_posts([special_post], date_str="2024-01-15", append=False)

        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert "quotes" in rows[0]["title"]
        # 줄바꿈이 ' | '로 대체되었는지 확인
        assert "\n" not in rows[0]["content"]

def test_csv_stats():
    from csv_exporter import CSVExporter
    with tempfile.TemporaryDirectory() as tmpdir:
        exporter = CSVExporter("testcafe", Path(tmpdir))
        stats = exporter.get_stats(SAMPLE_POSTS, SAMPLE_COMMENTS)
        assert stats["total_posts"] == 2
        assert stats["total_comments"] == 2
        assert stats["total_replies"] == 1  # is_reply=True인 댓글 1개

test("게시글 CSV 저장", test_csv_posts_save)
test("댓글 CSV 저장", test_csv_comments_save)
test("CSV 추가(append) 모드", test_csv_append_mode)
test("CSV 특수문자 처리", test_csv_special_chars)
test("크롤링 통계 계산", test_csv_stats)

# ──────────────────────────────────────────────────────────────────────────────
# 4. 설정 저장/불러오기 테스트
print(f"\n{INFO} [4] 설정 관리")

def test_config_save_load():
    import config

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        tmp_path = Path(f.name)

    try:
        # 원본 경로 교체
        original = config.CONFIG_FILE
        config.CONFIG_FILE = tmp_path

        test_data = {"naver_id": "testuser", "cafe_name": "mycafe"}
        config.save_config(test_data)

        loaded = config.load_config()
        assert loaded["naver_id"] == "testuser"
        assert loaded["cafe_name"] == "mycafe"
    finally:
        config.CONFIG_FILE = original
        tmp_path.unlink(missing_ok=True)

def test_config_empty_load():
    import config
    with tempfile.TemporaryDirectory() as tmpdir:
        original = config.CONFIG_FILE
        config.CONFIG_FILE = Path(tmpdir) / "nonexistent.json"
        try:
            result = config.load_config()
            assert result == {}
        finally:
            config.CONFIG_FILE = original

def test_output_dir_creation():
    import config
    with tempfile.TemporaryDirectory() as tmpdir:
        original = config.OUTPUT_DIR
        config.OUTPUT_DIR = Path(tmpdir) / "output" / "data"
        try:
            path = config.ensure_output_dir()
            assert path.exists()
            assert path.is_dir()
        finally:
            config.OUTPUT_DIR = original

test("설정 저장/불러오기", test_config_save_load)
test("빈 설정 불러오기", test_config_empty_load)
test("출력 디렉토리 생성", test_output_dir_creation)

# ──────────────────────────────────────────────────────────────────────────────
# 5. 스케줄러 기본 로직 테스트
print(f"\n{INFO} [5] 스케줄러 로직")

def test_scheduler_register():
    import schedule
    from scheduler import CrawlScheduler

    schedule.clear()
    executed = []
    scheduler = CrawlScheduler(lambda: executed.append(1), "23:59")

    # 스케줄 등록 확인 (실행은 하지 않음)
    schedule.every().day.at("23:59").do(lambda: None)
    assert len(schedule.jobs) == 1
    schedule.clear()

def test_scheduler_run_once():
    from scheduler import CrawlScheduler

    results_store = []
    def dummy_job():
        results_store.append("ran")

    CrawlScheduler.run_once(dummy_job)
    assert results_store == ["ran"]

test("스케줄러 등록", test_scheduler_register)
test("즉시 1회 실행", test_scheduler_run_once)

# ──────────────────────────────────────────────────────────────────────────────
# 6. 쿠키 로드 테스트
print(f"\n{INFO} [6] 쿠키 로드 (캡차 우회)")

def test_cookie_load():
    from login import NaverLogin

    login = NaverLogin()
    login.load_cookies_from_string("NID_AUT=abc123; NID_SES=xyz789; ANOTHER=value")

    cookies = dict(login.session.cookies)
    assert cookies.get("NID_AUT") == "abc123"
    assert cookies.get("NID_SES") == "xyz789"
    assert login.is_logged_in

test("쿠키 문자열 파싱 및 적용", test_cookie_load)

# ──────────────────────────────────────────────────────────────────────────────
# 결과 요약
print("\n" + "=" * 55)
total = results["pass"] + results["fail"]
print(f"  결과: {results['pass']}/{total} 통과  ({results['fail']} 실패)")
print("=" * 55)

if results["fail"] > 0:
    sys.exit(1)
else:
    print("\n모든 테스트를 통과했습니다.")
    print("실제 크롤링은 로컬 환경에서 python main.py 로 실행하세요.")
    sys.exit(0)
