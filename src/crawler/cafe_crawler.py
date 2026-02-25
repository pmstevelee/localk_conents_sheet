"""
네이버 카페 크롤러 메인 클래스
전체 크롤링 흐름 조율
"""
import re
import time
import logging
from typing import List, Optional
from urllib.parse import urlparse, parse_qs, unquote

import sys
sys.path.append(str(__file__).rsplit('/', 3)[0])
from src.utils.browser import BrowserManager
from src.utils.iframe_handler import IframeHandler
from src.auth.naver_login import NaverLogin, NaverLoginError, CaptchaDetectedError
from src.crawler.board_parser import BoardParser, Board
from src.crawler.post_parser import PostParser, Post
from src.storage.csv_handler import CSVHandler
from config.settings import OUTPUT_DIR, exclude_keywords_manager

logger = logging.getLogger(__name__)


class CrawlerError(Exception):
    """크롤러 관련 예외"""
    pass


class CafeCrawler:
    """네이버 카페 크롤러"""

    def __init__(
        self,
        cafe_id: str,
        user_id: str,
        password: str,
        headless: bool = False,
        manual_login: bool = False,
        exclude_keywords: List[str] = None
    ):
        """
        Args:
            cafe_id: 네이버 카페 ID (URL의 카페명)
            user_id: 네이버 아이디
            password: 네이버 비밀번호
            headless: 헤드리스 모드 사용 여부
            manual_login: 수동 로그인 모드
            exclude_keywords: 수집 제외 키워드 목록 (None이면 전역 설정 사용)
        """
        self.cafe_id = cafe_id
        self.user_id = user_id
        self.password = password
        self.headless = headless
        self.manual_login = manual_login
        # 제외 키워드: 파라미터로 전달받거나 전역 설정 사용
        self.exclude_keywords = exclude_keywords if exclude_keywords is not None else exclude_keywords_manager.get_keywords()

        self.browser_manager = None
        self.driver = None
        self.iframe_handler = None
        self._is_initialized = False
        self._is_logged_in = False

    def start(self):
        """크롤러 초기화 및 브라우저 시작"""
        logger.info("크롤러 시작...")

        try:
            # 브라우저 시작
            self.browser_manager = BrowserManager(headless=self.headless)
            self.driver = self.browser_manager.create_driver()

            # iframe 핸들러 초기화
            self.iframe_handler = IframeHandler(self.driver)

            self._is_initialized = True
            logger.info("브라우저 초기화 완료")

        except Exception as e:
            logger.error(f"크롤러 초기화 실패: {e}")
            self.close()
            raise CrawlerError(f"초기화 실패: {e}")

    def login(self) -> bool:
        """
        네이버 로그인

        Returns:
            로그인 성공 여부

        Raises:
            CrawlerError: 초기화되지 않은 경우
            CaptchaDetectedError: 캡차 감지 시
        """
        if not self._is_initialized:
            raise CrawlerError("크롤러가 초기화되지 않았습니다. start()를 먼저 호출하세요.")

        try:
            # 수동 로그인 모드: 카페에서 시작하여 로그인 후 돌아옴
            if self.manual_login:
                return self._manual_login_from_cafe()

            login_handler = NaverLogin(self.driver, manual_mode=False)
            success = login_handler.login(self.user_id, self.password)

            if success:
                self._is_logged_in = True
                logger.info("로그인 성공")

                # 카페로 이동
                if login_handler.navigate_to_cafe(self.cafe_id):
                    logger.info(f"카페 '{self.cafe_id}' 접속 완료")
                    return True
                else:
                    logger.warning("카페 접속 실패")
                    return False

            return False

        except CaptchaDetectedError:
            logger.error("캡차가 감지되었습니다. 수동 로그인이 필요합니다.")
            raise
        except NaverLoginError as e:
            logger.error(f"로그인 실패: {e}")
            return False
        except Exception as e:
            logger.error(f"로그인 중 예외 발생: {e}")
            return False

    def _manual_login_from_cafe(self) -> bool:
        """카페 페이지에서 시작하여 수동 로그인"""
        cafe_url = f"https://cafe.naver.com/{self.cafe_id}"
        logger.info(f"카페로 이동: {cafe_url}")
        self.driver.get(cafe_url)
        time.sleep(3)

        print("\n" + "=" * 50)
        print("브라우저에서 로그인해주세요.")
        print("로그인 후 카페 페이지로 돌아오면 자동으로 진행됩니다.")
        print("최대 120초 동안 대기합니다...")
        print("=" * 50)

        # 로그인 완료 대기
        start_time = time.time()
        timeout = 120

        while time.time() - start_time < timeout:
            current_url = self.driver.current_url
            # 카페 페이지에 있고 로그인 페이지가 아니면 완료
            if "cafe.naver.com" in current_url and "nidlogin" not in current_url:
                # iframe이 있는지 확인 (로그인 완료 시)
                try:
                    from selenium.webdriver.common.by import By
                    self.driver.find_element(By.ID, "cafe_main")
                    logger.info("로그인 및 카페 접속 완료")
                    self._is_logged_in = True
                    return True
                except:
                    pass
            time.sleep(2)

        logger.error("로그인 시간 초과")
        return False

    def get_boards(self) -> List[Board]:
        """
        카페 게시판 목록 조회

        Returns:
            게시판 목록
        """
        if not self._is_logged_in:
            raise CrawlerError("로그인이 필요합니다.")

        board_parser = BoardParser(self.driver, self.iframe_handler)
        return board_parser.get_board_list(self.cafe_id)

    def select_board_interactive(self, boards: List[Board]) -> Optional[Board]:
        """
        대화형 게시판 선택

        Args:
            boards: 게시판 목록

        Returns:
            선택된 게시판 또는 None
        """
        board_parser = BoardParser(self.driver, self.iframe_handler)
        return board_parser.select_board_interactive(boards)

    def find_board(self, boards: List[Board], identifier: str) -> Optional[Board]:
        """
        ID 또는 이름으로 게시판 찾기

        Args:
            boards: 게시판 목록
            identifier: 게시판 ID 또는 이름

        Returns:
            찾은 게시판 또는 None
        """
        board_parser = BoardParser(self.driver, self.iframe_handler)

        # ID로 먼저 검색
        board = board_parser.get_board_by_id(boards, identifier)
        if board:
            return board

        # 이름으로 검색
        return board_parser.get_board_by_name(boards, identifier)

    def parse_board_url(self, url: str) -> Optional[Board]:
        """
        게시판 URL에서 Board 객체 생성

        Args:
            url: 게시판 URL

        Returns:
            Board 객체 또는 None

        지원 URL 형식:
            - https://cafe.naver.com/cafeid?menuid=123
            - https://cafe.naver.com/cafeid?iframe_url=/ArticleList.nhn?search.menuid=123
            - https://cafe.naver.com/ArticleList.nhn?search.clubid=xxx&search.menuid=123
            - https://cafe.naver.com/f-e/cafes/25760765/menus/165 (새 형식)
        """
        if not url:
            return None

        try:
            # URL 디코딩
            url = unquote(url)

            # club_id 추출 패턴들
            club_id = ""
            club_patterns = [
                r'/cafes/(\d+)',           # 새 형식: /f-e/cafes/25760765/menus/165
                r'clubid=(\d+)',
                r'search\.clubid=(\d+)',
            ]

            for pattern in club_patterns:
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    club_id = match.group(1)
                    break

            # menuid 추출 패턴들
            menu_patterns = [
                r'/menus/(\d+)',           # 새 형식: /f-e/cafes/xxx/menus/165
                r'menuid=(\d+)',
                r'search\.menuid=(\d+)',
                r'menuId=(\d+)',
            ]

            board_id = None
            for pattern in menu_patterns:
                match = re.search(pattern, url, re.IGNORECASE)
                if match:
                    board_id = match.group(1)
                    break

            if not board_id:
                logger.error(f"URL에서 게시판 ID를 찾을 수 없습니다: {url}")
                return None

            # 게시판 이름은 URL에서 알 수 없으므로 ID를 이름으로 사용
            board_name = f"게시판_{board_id}"

            # 전체 URL 구성
            if club_id:
                full_url = f"https://cafe.naver.com/{self.cafe_id}?iframe_url=/ArticleList.nhn%3Fsearch.clubid={club_id}%26search.menuid={board_id}"
            else:
                full_url = f"https://cafe.naver.com/{self.cafe_id}?iframe_url=/ArticleList.nhn%3Fsearch.menuid={board_id}"

            board = Board(
                board_id=board_id,
                name=board_name,
                url=full_url,
                club_id=club_id
            )

            logger.info(f"URL에서 게시판 정보 추출: ID={board_id}, ClubID={club_id}")
            return board

        except Exception as e:
            logger.error(f"게시판 URL 파싱 실패: {e}")
            return None

    def crawl_today_posts(self, board: Board) -> List[Post]:
        """
        특정 게시판의 오늘 게시글 크롤링

        Args:
            board: 크롤링할 게시판

        Returns:
            오늘 작성된 게시글 목록 (댓글 포함)
        """
        return self.crawl_posts(board, today_only=True)

    def crawl_posts(
        self,
        board: Board,
        max_posts: int = 20,
        max_pages: int = 1,
        today_only: bool = False
    ) -> List[Post]:
        """
        특정 게시판의 게시글 크롤링

        Args:
            board: 크롤링할 게시판
            max_posts: 최대 수집 게시글 수
            max_pages: 최대 조회 페이지 수
            today_only: True면 오늘 작성된 글만 수집

        Returns:
            게시글 목록 (댓글 포함)
        """
        if not self._is_logged_in:
            raise CrawlerError("로그인이 필요합니다.")

        logger.info(f"게시판 '{board.name}' 크롤링 시작...")
        if self.exclude_keywords:
            logger.info(f"제외 키워드: {self.exclude_keywords}")

        # club_id가 있으면 전달
        club_id = getattr(board, 'club_id', '') or ''
        post_parser = PostParser(
            self.driver,
            self.iframe_handler,
            self.cafe_id,
            club_id,
            exclude_keywords=self.exclude_keywords
        )
        posts = post_parser.crawl_posts(
            board.board_id,
            max_posts=max_posts,
            max_pages=max_pages,
            today_only=today_only
        )

        logger.info(f"크롤링 완료: {len(posts)}개 게시글")
        return posts

    def save_to_csv(
        self,
        posts: List[Post],
        board_name: str,
        compact: bool = False
    ) -> str:
        """
        게시글을 CSV로 저장

        Args:
            posts: 저장할 게시글 목록
            board_name: 게시판 이름
            compact: 컴팩트 형식 사용 여부

        Returns:
            저장된 파일 경로
        """
        csv_handler = CSVHandler()

        if compact:
            return csv_handler.save_posts_compact(posts, self.cafe_id, board_name)
        else:
            return csv_handler.save_posts(posts, self.cafe_id, board_name)

    def run(self, board_identifier: str = None) -> str:
        """
        크롤링 전체 흐름 실행

        Args:
            board_identifier: 게시판 ID 또는 이름 (None이면 대화형 선택)

        Returns:
            저장된 CSV 파일 경로
        """
        try:
            # 1. 시작
            self.start()

            # 2. 로그인
            if not self.login():
                raise CrawlerError("로그인 실패")

            # 3. 게시판 목록 조회
            boards = self.get_boards()
            if not boards:
                raise CrawlerError("게시판 목록을 가져올 수 없습니다.")

            # 4. 게시판 선택
            board = None
            if board_identifier:
                board = self.find_board(boards, board_identifier)
                if not board:
                    logger.warning(f"게시판 '{board_identifier}'을(를) 찾을 수 없습니다. 대화형 선택으로 전환합니다.")

            if not board:
                board = self.select_board_interactive(boards)

            if not board:
                raise CrawlerError("게시판이 선택되지 않았습니다.")

            logger.info(f"선택된 게시판: {board.name} (ID: {board.board_id})")

            # 5. 오늘 게시글 크롤링
            posts = self.crawl_today_posts(board)

            if not posts:
                logger.info("오늘 작성된 게시글이 없습니다.")
                return ""

            # 6. CSV 저장
            filepath = self.save_to_csv(posts, board.name)

            # 7. 결과 요약
            total_comments = sum(len(p.comments) for p in posts)
            logger.info(f"\n=== 크롤링 완료 ===")
            logger.info(f"게시글: {len(posts)}개")
            logger.info(f"총 댓글: {total_comments}개")
            logger.info(f"저장 파일: {filepath}")

            return filepath

        except Exception as e:
            logger.error(f"크롤링 중 오류: {e}")
            raise

        finally:
            self.close()

    def close(self):
        """리소스 정리 및 브라우저 종료"""
        if self.browser_manager:
            try:
                self.browser_manager.close()
            except:
                pass
            finally:
                self.browser_manager = None
                self.driver = None
                self.iframe_handler = None
                self._is_initialized = False
                self._is_logged_in = False

        logger.info("크롤러 종료")

    def __enter__(self):
        """Context manager 진입"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.close()
        return False
