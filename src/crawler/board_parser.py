"""
네이버 카페 게시판 파싱
카페 내 게시판 목록 조회 및 선택
"""
import time
import logging
from dataclasses import dataclass
from typing import List, Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException
)

import sys
sys.path.append(str(__file__).rsplit('/', 3)[0])
from src.utils.iframe_handler import IframeHandler

logger = logging.getLogger(__name__)


@dataclass
class Board:
    """게시판 정보"""
    board_id: str       # 게시판 ID (menuid 값)
    name: str           # 게시판 이름
    url: str            # 게시판 URL
    menu_type: str = "" # 메뉴 타입 (일반 게시판, 폴더 등)
    club_id: str = ""   # 카페 클럽 ID


class BoardParser:
    """게시판 목록 파싱 클래스"""

    # 게시판 목록 셀렉터
    MENU_LIST_SELECTOR = "ul.cafe-menu-list"
    MENU_ITEM_SELECTOR = "ul.cafe-menu-list > li"
    MENU_LINK_SELECTOR = "a.cafe-menu-link"

    def __init__(self, driver: WebDriver, iframe_handler: IframeHandler):
        """
        Args:
            driver: Selenium WebDriver
            iframe_handler: iframe 전환 핸들러
        """
        self.driver = driver
        self.iframe_handler = iframe_handler

    def get_board_list(self, cafe_id: str) -> List[Board]:
        """
        카페의 게시판 목록 조회

        Args:
            cafe_id: 카페 ID

        Returns:
            게시판 목록
        """
        boards = []

        try:
            # 카페 메인 페이지로 이동
            cafe_url = f"https://cafe.naver.com/{cafe_id}"
            self.driver.get(cafe_url)
            time.sleep(2)

            # iframe 전환
            if not self.iframe_handler.switch_to_cafe_main():
                logger.error("카페 iframe 전환 실패")
                return boards

            # 메뉴 목록 대기
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, self.MENU_LIST_SELECTOR)
                    )
                )
            except TimeoutException:
                logger.warning("메뉴 목록을 찾을 수 없음, 대체 셀렉터 시도")
                # 대체 셀렉터 시도
                pass

            # 게시판 항목 파싱
            boards = self._parse_menu_items(cafe_id)

            logger.info(f"총 {len(boards)}개의 게시판 발견")
            return boards

        except Exception as e:
            logger.error(f"게시판 목록 조회 중 오류: {e}")
            return boards

    def _parse_menu_items(self, cafe_id: str) -> List[Board]:
        """
        메뉴 항목들을 파싱하여 게시판 목록 반환

        Args:
            cafe_id: 카페 ID

        Returns:
            게시판 목록
        """
        boards = []

        try:
            # 모든 링크에서 menuid가 포함된 것 찾기
            all_links = self.driver.find_elements(By.TAG_NAME, "a")
            menu_links = []

            for link in all_links:
                href = link.get_attribute("href") or ""
                if "menuid" in href.lower() and "ArticleList" in href:
                    menu_links.append(link)

            if menu_links:
                logger.debug(f"메뉴 링크 발견: {len(menu_links)}개")

            seen_ids = set()  # 중복 제거용

            for link in menu_links:
                try:
                    href = link.get_attribute("href") or ""
                    name = link.text.strip()

                    # 빈 이름이나 "더보기" 건너뛰기
                    if not name or name == "더보기":
                        continue

                    # menuid 추출
                    board_id = self._extract_menu_id(href)
                    if not board_id:
                        continue

                    # 중복 제거
                    if board_id in seen_ids:
                        continue
                    seen_ids.add(board_id)

                    # 전체 URL 구성
                    if href.startswith("/"):
                        url = f"https://cafe.naver.com{href}"
                    elif href.startswith("http"):
                        url = href
                    else:
                        url = f"https://cafe.naver.com/{cafe_id}?iframe_url=/ArticleList.nhn%3Fsearch.clubid=0%26search.menuid={board_id}"

                    board = Board(
                        board_id=board_id,
                        name=name,
                        url=url
                    )
                    boards.append(board)

                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    logger.debug(f"메뉴 항목 파싱 중 오류: {e}")
                    continue

        except Exception as e:
            logger.error(f"메뉴 파싱 중 오류: {e}")

        return boards

    def _parse_menu_via_js(self, cafe_id: str) -> List[Board]:
        """JavaScript를 통한 메뉴 파싱"""
        boards = []

        try:
            script = """
            var boards = [];
            var menuItems = document.querySelectorAll('.cafe-menu-list li a, #menuLink a, .menu a');
            menuItems.forEach(function(item) {
                var href = item.getAttribute('href') || '';
                var name = item.innerText.trim();
                if (name && href) {
                    boards.push({href: href, name: name});
                }
            });
            return boards;
            """

            result = self.driver.execute_script(script)

            for item in result:
                href = item.get('href', '')
                name = item.get('name', '')

                board_id = self._extract_menu_id(href)
                if board_id and name:
                    boards.append(Board(
                        board_id=board_id,
                        name=name,
                        url=href if href.startswith('http') else f"https://cafe.naver.com{href}"
                    ))

        except Exception as e:
            logger.error(f"JavaScript 메뉴 파싱 실패: {e}")

        return boards

    def _extract_menu_id(self, href: str) -> str:
        """
        URL에서 menuid 추출

        Args:
            href: 링크 URL

        Returns:
            메뉴 ID 문자열
        """
        if not href:
            return ""

        # menuid 파라미터 추출
        import re

        patterns = [
            r'menuid=(\d+)',
            r'search\.menuid=(\d+)',
            r'/(\d+)$',
        ]

        for pattern in patterns:
            match = re.search(pattern, href)
            if match:
                return match.group(1)

        return ""

    def select_board_interactive(self, boards: List[Board]) -> Optional[Board]:
        """
        대화형으로 게시판 선택

        Args:
            boards: 게시판 목록

        Returns:
            선택된 게시판 또는 None
        """
        if not boards:
            print("선택 가능한 게시판이 없습니다.")
            return None

        print("\n" + "=" * 50)
        print("게시판 목록")
        print("=" * 50)

        for idx, board in enumerate(boards, 1):
            print(f"  {idx:3d}. {board.name}")

        print("=" * 50)

        while True:
            try:
                choice = input("\n게시판 번호를 선택하세요 (0: 취소): ").strip()

                if choice == "0":
                    return None

                choice_num = int(choice)

                if 1 <= choice_num <= len(boards):
                    selected = boards[choice_num - 1]
                    print(f"\n선택된 게시판: {selected.name}")
                    return selected
                else:
                    print(f"1-{len(boards)} 사이의 숫자를 입력하세요.")

            except ValueError:
                print("올바른 숫자를 입력하세요.")
            except KeyboardInterrupt:
                print("\n취소되었습니다.")
                return None

    def get_board_by_id(self, boards: List[Board], board_id: str) -> Optional[Board]:
        """
        ID로 게시판 검색

        Args:
            boards: 게시판 목록
            board_id: 찾을 게시판 ID

        Returns:
            해당 게시판 또는 None
        """
        for board in boards:
            if board.board_id == board_id:
                return board
        return None

    def get_board_by_name(self, boards: List[Board], name: str) -> Optional[Board]:
        """
        이름으로 게시판 검색 (부분 일치)

        Args:
            boards: 게시판 목록
            name: 찾을 게시판 이름

        Returns:
            해당 게시판 또는 None
        """
        name = name.strip().lower()

        # 정확히 일치
        for board in boards:
            if board.name.strip().lower() == name:
                return board

        # 부분 일치
        for board in boards:
            if name in board.name.strip().lower():
                return board

        return None
