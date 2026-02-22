"""
네이버 카페 크롤러 - 메인 실행 파일
대화형 CLI로 카페, 게시판 선택 후 크롤링 실행
"""

import sys
import getpass
import time
from datetime import datetime
from pathlib import Path

import config
from login import NaverLogin, NaverLoginError
from cafe_manager import CafeManager, CafeError
from crawler import BoardCrawler
from csv_exporter import CSVExporter
from scheduler import CrawlScheduler


# ──────────────────────────────────────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────────────────────────────────────

def banner():
    print("=" * 60)
    print("   네이버 카페 크롤러 v1.0")
    print("   게시글 + 댓글 자동 수집 → CSV 저장")
    print("=" * 60)
    print()


def ask_int(prompt: str, min_val: int = 1, max_val: int = 999) -> int:
    """정수 입력 유효성 검사"""
    while True:
        try:
            val = int(input(prompt).strip())
            if min_val <= val <= max_val:
                return val
            print(f"  {min_val}~{max_val} 사이의 숫자를 입력하세요.")
        except ValueError:
            print("  숫자를 입력하세요.")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Y/N 입력"""
    hint = "[Y/n]" if default else "[y/N]"
    while True:
        val = input(f"{prompt} {hint}: ").strip().lower()
        if val == "" :
            return default
        if val in ("y", "yes"):
            return True
        if val in ("n", "no"):
            return False
        print("  y 또는 n을 입력하세요.")


# ──────────────────────────────────────────────────────────────────────────────
# Step 1: 로그인
# ──────────────────────────────────────────────────────────────────────────────

def do_login() -> NaverLogin:
    """네이버 로그인 수행, NaverLogin 객체 반환"""
    print("[1단계] 네이버 로그인")
    print("-" * 40)

    saved = config.load_config()
    naver_login = NaverLogin()

    # 쿠키 직접 입력 옵션 (캡차/2FA 우회용)
    print("로그인 방식을 선택하세요:")
    print("  1. 아이디/비밀번호 자동 로그인")
    print("  2. 브라우저 쿠키 수동 입력 (캡차/2FA 발생 시)")

    choice = ask_int("선택 > ", 1, 2)

    if choice == 2:
        print("\n브라우저에서 네이버 로그인 후 개발자 도구(F12) → Application → Cookies에서")
        print("NID_AUT, NID_SES 값을 'key=value; key2=value2' 형식으로 붙여넣으세요.")
        cookie_str = input("쿠키 > ").strip()
        if not cookie_str:
            print("쿠키를 입력하지 않았습니다.")
            sys.exit(1)
        naver_login.load_cookies_from_string(cookie_str)
        print("쿠키가 적용되었습니다.")
        return naver_login

    # 아이디/비밀번호 로그인
    default_id = saved.get("naver_id", "")
    id_hint = f" [{default_id}]" if default_id else ""
    naver_id = input(f"네이버 아이디{id_hint}: ").strip() or default_id

    if not naver_id:
        print("아이디를 입력하세요.")
        sys.exit(1)

    password = getpass.getpass("비밀번호: ")

    if not password:
        print("비밀번호를 입력하세요.")
        sys.exit(1)

    print("\n로그인 중...")
    try:
        naver_login.login(naver_id, password)
        print("로그인 성공!")

        # 아이디 저장 (비밀번호는 저장하지 않음)
        saved["naver_id"] = naver_id
        config.save_config(saved)

    except NaverLoginError as e:
        print(f"\n[로그인 오류] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[예상치 못한 오류] {e}")
        sys.exit(1)

    return naver_login


# ──────────────────────────────────────────────────────────────────────────────
# Step 2: 카페 선택
# ──────────────────────────────────────────────────────────────────────────────

def select_cafe(naver_login: NaverLogin) -> tuple[str, str, CafeManager]:
    """카페 이름 입력 및 ID 조회, (cafe_name, cafe_id, manager) 반환"""
    print("\n[2단계] 카페 선택")
    print("-" * 40)

    saved = config.load_config()
    default_cafe = saved.get("cafe_name", "")
    hint = f" [{default_cafe}]" if default_cafe else ""

    print("카페 URL 예시: https://cafe.naver.com/myCafe → 'myCafe' 입력")
    cafe_name = input(f"카페 이름(URL 슬러그){hint}: ").strip() or default_cafe

    if not cafe_name:
        print("카페 이름을 입력하세요.")
        sys.exit(1)

    session = naver_login.get_session()
    manager = CafeManager(session)

    print(f"\n'{cafe_name}' 카페 정보 조회 중...")
    try:
        cafe_id = manager.get_cafe_id(cafe_name)
        print(f"카페 ID: {cafe_id}")
    except CafeError as e:
        print(f"[오류] {e}")
        sys.exit(1)

    saved["cafe_name"] = cafe_name
    config.save_config(saved)

    return cafe_name, cafe_id, manager


# ──────────────────────────────────────────────────────────────────────────────
# Step 3: 게시판 선택
# ──────────────────────────────────────────────────────────────────────────────

def select_boards(manager: CafeManager, cafe_name: str) -> list[dict]:
    """게시판 목록 조회 및 선택, 선택된 게시판 리스트 반환"""
    print("\n[3단계] 게시판 선택")
    print("-" * 40)

    print("게시판 목록 불러오는 중...")
    try:
        boards = manager.get_boards(cafe_name)
    except CafeError as e:
        print(f"[오류] {e}")
        sys.exit(1)

    print(f"\n총 {len(boards)}개 게시판:")
    for i, board in enumerate(boards, 1):
        print(f"  {i:3d}. {board['name']}")

    print("\n크롤링할 게시판을 선택하세요.")
    print("  - 번호 입력: 특정 게시판 선택 (예: 1)")
    print("  - 여러 개:   쉼표로 구분 (예: 1,3,5)")
    print("  - 전체:      'all' 입력")

    while True:
        sel = input("선택 > ").strip().lower()
        if sel == "all":
            return boards
        try:
            indices = [int(x.strip()) - 1 for x in sel.split(",")]
            selected = [boards[i] for i in indices if 0 <= i < len(boards)]
            if selected:
                print(f"\n선택된 게시판: {', '.join(b['name'] for b in selected)}")
                return selected
            print("  유효한 번호를 입력하세요.")
        except (ValueError, IndexError):
            print("  올바른 형식으로 입력하세요. (예: 1 또는 1,2,3 또는 all)")


# ──────────────────────────────────────────────────────────────────────────────
# Step 4: 크롤링 옵션 설정
# ──────────────────────────────────────────────────────────────────────────────

def get_crawl_options() -> dict:
    """크롤링 옵션 입력"""
    print("\n[4단계] 크롤링 옵션")
    print("-" * 40)

    include_comments = ask_yes_no("댓글도 크롤링하시겠습니까?", default=True)

    print("\n크롤링 페이지 수 제한:")
    print("  0 = 전체 페이지 (시간이 오래 걸릴 수 있음)")
    max_pages_input = input("최대 페이지 수 [0=전체]: ").strip()
    try:
        max_pages = int(max_pages_input) or None
    except ValueError:
        max_pages = None

    run_mode = 0
    print("\n실행 모드:")
    print("  1. 지금 즉시 1회 실행")
    print("  2. 매일 자동 실행 (스케줄러)")
    print("  3. 즉시 실행 후 매일 자동 실행")
    run_mode = ask_int("선택 > ", 1, 3)

    schedule_time = config.DEFAULT_SCHEDULE_TIME
    if run_mode in (2, 3):
        print(f"\n자동 실행 시간 (기본값: {config.DEFAULT_SCHEDULE_TIME})")
        t = input("실행 시간 [HH:MM]: ").strip()
        if t and len(t) == 5 and t[2] == ":":
            schedule_time = t

    return {
        "include_comments": include_comments,
        "max_pages": max_pages,
        "run_mode": run_mode,
        "schedule_time": schedule_time,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 크롤링 실행
# ──────────────────────────────────────────────────────────────────────────────

def run_crawl(
    session,
    cafe_id: str,
    cafe_name: str,
    selected_boards: list[dict],
    options: dict,
) -> None:
    """실제 크롤링 수행"""
    crawler = BoardCrawler(session, cafe_id, cafe_name)
    exporter = CSVExporter(cafe_name)
    date_str = datetime.now().strftime("%Y-%m-%d")

    all_posts = []
    all_comments = []

    print(f"\n크롤링 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"대상 게시판: {len(selected_boards)}개\n")

    for board in selected_boards:
        print(f"[게시판] {board['name']} (ID: {board['id']})")
        posts, comments = crawler.crawl_board(
            menu_id=board["id"],
            max_pages=options["max_pages"],
            include_comments=options["include_comments"],
        )
        all_posts.extend(posts)
        all_comments.extend(comments)
        print(f"  → 게시글 {len(posts)}개, 댓글 {len(comments)}개 수집")
        time.sleep(config.CRAWL_DELAY * 2)

    # CSV 저장
    posts_path, comments_path = exporter.save_all(
        all_posts, all_comments, date_str=date_str
    )
    exporter.print_stats(all_posts, all_comments, posts_path, comments_path)


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────

def main():
    banner()

    # 로그인
    naver_login = do_login()
    session = naver_login.get_session()

    # 카페 선택
    cafe_name, cafe_id, manager = select_cafe(naver_login)

    # 게시판 선택
    selected_boards = select_boards(manager, cafe_name)

    # 크롤링 옵션
    options = get_crawl_options()

    # 크롤링 실행 함수 정의
    def crawl_job():
        run_crawl(session, cafe_id, cafe_name, selected_boards, options)

    # 실행 모드에 따라 분기
    run_mode = options["run_mode"]

    if run_mode == 1:
        # 즉시 1회 실행
        CrawlScheduler.run_once(crawl_job)

    elif run_mode == 2:
        # 스케줄만 등록 (즉시 실행 안 함)
        scheduler = CrawlScheduler(crawl_job, options["schedule_time"])
        scheduler.start(run_immediately=False)

    elif run_mode == 3:
        # 즉시 실행 + 스케줄 등록
        scheduler = CrawlScheduler(crawl_job, options["schedule_time"])
        scheduler.start(run_immediately=True)

    # 로그아웃
    naver_login.logout()
    print("프로그램이 종료되었습니다.")


if __name__ == "__main__":
    main()
