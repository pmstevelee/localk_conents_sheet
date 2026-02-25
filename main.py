#!/usr/bin/env python3
"""
네이버 카페 크롤러 CLI
매일 특정 게시판의 오늘 작성된 글과 댓글을 CSV로 저장
"""
import argparse
import logging
import sys
import os
from getpass import getpass
from datetime import datetime

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.crawler.cafe_crawler import CafeCrawler, CrawlerError
from src.auth.naver_login import CaptchaDetectedError
from config.settings import LOG_DIR


def setup_logging(verbose: bool = False):
    """로깅 설정"""
    level = logging.DEBUG if verbose else logging.INFO

    # 로그 포맷
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))

    # 파일 핸들러
    log_filename = datetime.now().strftime("crawler_%Y%m%d.log")
    file_handler = logging.FileHandler(
        LOG_DIR / log_filename,
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # selenium/urllib3 로거 레벨 조정
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('webdriver_manager').setLevel(logging.WARNING)


def parse_args():
    """명령줄 인수 파싱"""
    parser = argparse.ArgumentParser(
        description='네이버 카페 크롤러 - 오늘 작성된 게시글과 댓글을 CSV로 저장',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 대화형 모드 (게시판 선택)
  python main.py --cafe mycafe --user myid

  # 특정 게시판 지정
  python main.py --cafe mycafe --user myid --board "자유게시판"

  # 게시판 ID로 지정
  python main.py --cafe mycafe --user myid --board 123

  # 게시판 URL로 직접 지정
  python main.py --cafe mycafe --user myid --board-url "https://cafe.naver.com/mycafe?menuid=123"

  # 비밀번호도 함께 지정 (자동화용)
  python main.py --cafe mycafe --user myid --password mypass --board 123
        """
    )

    parser.add_argument(
        '--cafe', '-c',
        required=True,
        help='네이버 카페 ID (URL의 카페명, 예: mycafe)'
    )

    parser.add_argument(
        '--user', '-u',
        required=True,
        help='네이버 아이디'
    )

    parser.add_argument(
        '--password', '-p',
        default=None,
        help='네이버 비밀번호 (미입력시 프롬프트)'
    )

    parser.add_argument(
        '--board', '-b',
        default=None,
        help='게시판 ID 또는 이름 (미입력시 대화형 선택)'
    )

    parser.add_argument(
        '--board-url',
        default=None,
        help='게시판 URL 직접 입력 (예: https://cafe.naver.com/mycafe?menuid=123)'
    )

    parser.add_argument(
        '--headless',
        action='store_true',
        help='헤드리스 모드 (브라우저 화면 없이 실행, 봇 탐지 위험 있음)'
    )

    parser.add_argument(
        '--manual-login',
        action='store_true',
        help='수동 로그인 모드 (브라우저에서 직접 로그인)'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='상세 로그 출력'
    )

    parser.add_argument(
        '--compact',
        action='store_true',
        help='컴팩트 CSV 형식 (게시글당 1행, 댓글은 JSON)'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='오늘 날짜 필터 없이 모든 게시글 수집'
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=20,
        help='수집할 최대 게시글 수 (기본값: 20)'
    )

    parser.add_argument(
        '--pages',
        type=int,
        default=1,
        help='조회할 페이지 수 (기본값: 1)'
    )

    return parser.parse_args()


def main():
    """메인 함수"""
    args = parse_args()

    # 로깅 설정
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    print("\n" + "=" * 60)
    print("네이버 카페 크롤러")
    print("=" * 60)
    print(f"카페: {args.cafe}")
    print(f"사용자: {args.user}")
    print("=" * 60 + "\n")

    # 비밀번호 입력
    password = args.password
    if not password:
        try:
            password = getpass("네이버 비밀번호를 입력하세요: ")
        except KeyboardInterrupt:
            print("\n취소되었습니다.")
            sys.exit(0)

    if not password:
        print("비밀번호가 입력되지 않았습니다.")
        sys.exit(1)

    # 크롤러 실행
    crawler = None
    try:
        crawler = CafeCrawler(
            cafe_id=args.cafe,
            user_id=args.user,
            password=password,
            headless=args.headless,
            manual_login=args.manual_login
        )

        # 시작
        crawler.start()

        # 로그인
        logger.info("로그인 시도 중...")
        if not crawler.login():
            logger.error("로그인에 실패했습니다.")
            sys.exit(1)

        # 게시판 선택
        board = None

        # 게시판 URL이 직접 입력된 경우
        if args.board_url:
            logger.info("게시판 URL에서 정보 추출 중...")
            board = crawler.parse_board_url(args.board_url)
            if not board:
                logger.error(f"게시판 URL을 파싱할 수 없습니다: {args.board_url}")
                sys.exit(1)
        else:
            # 게시판 목록 조회
            logger.info("게시판 목록 조회 중...")
            boards = crawler.get_boards()

            if not boards:
                logger.error("게시판 목록을 가져올 수 없습니다.")
                sys.exit(1)

            logger.info(f"{len(boards)}개의 게시판을 찾았습니다.")

            if args.board:
                board = crawler.find_board(boards, args.board)
                if not board:
                    logger.warning(f"'{args.board}' 게시판을 찾을 수 없습니다.")

            if not board:
                board = crawler.select_board_interactive(boards)

        if not board:
            logger.info("게시판 선택이 취소되었습니다.")
            sys.exit(0)

        print(f"\n선택된 게시판: {board.name} (ID: {board.board_id})\n")

        # 게시글 크롤링
        if args.all:
            logger.info(f"게시글 크롤링 중... (최대 {args.limit}개, {args.pages}페이지)")
            posts = crawler.crawl_posts(board, max_posts=args.limit, max_pages=args.pages, today_only=False)
        else:
            logger.info("오늘 작성된 게시글 크롤링 중...")
            posts = crawler.crawl_posts(board, max_posts=args.limit, max_pages=args.pages, today_only=True)

        if not posts:
            print("\n수집된 게시글이 없습니다.")
            sys.exit(0)

        # CSV 저장
        logger.info("CSV 파일 저장 중...")
        if args.compact:
            filepath = crawler.save_to_csv(posts, board.name, compact=True)
        else:
            filepath = crawler.save_to_csv(posts, board.name)

        # 결과 출력
        total_comments = sum(len(p.comments) for p in posts)

        print("\n" + "=" * 60)
        print("크롤링 완료!")
        print("=" * 60)
        print(f"수집된 게시글: {len(posts)}개")
        print(f"수집된 댓글: {total_comments}개")
        print(f"저장 파일: {filepath}")
        print("=" * 60 + "\n")

    except CaptchaDetectedError:
        logger.error("\n캡차가 감지되었습니다.")
        logger.error("잠시 후 다시 시도하거나, 수동으로 로그인 후 재시도해주세요.")
        sys.exit(1)

    except CrawlerError as e:
        logger.error(f"크롤링 오류: {e}")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        sys.exit(0)

    except Exception as e:
        logger.exception(f"예기치 않은 오류: {e}")
        sys.exit(1)

    finally:
        if crawler:
            crawler.close()


if __name__ == "__main__":
    main()
