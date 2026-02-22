"""
네이버 카페 게시판 관리 모듈
- 카페 정보 조회
- 게시판 목록 가져오기
- 카페 ID 변환
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from typing import Optional

import config


class CafeError(Exception):
    pass


class CafeManager:
    def __init__(self, session: requests.Session):
        self.session = session
        self._cafe_id: Optional[str] = None
        self._cafe_name: Optional[str] = None

    def get_cafe_id(self, cafe_name: str) -> str:
        """
        카페 이름(URL 슬러그)으로 카페 숫자 ID 조회
        예: 'mycafe' → '12345678'
        """
        url = f"{config.NAVER_CAFE_BASE_URL}/{cafe_name}"
        resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()

        # cafe.naver.com/mycafe 접속 시 실제 카페 ID가 포함된 URL로 리디렉트됨
        # 또는 HTML에서 cafeid 파라미터 추출
        soup = BeautifulSoup(resp.text, "lxml")

        # 방법 1: meta 태그에서 추출
        canonical = soup.find("link", rel="canonical")
        if canonical:
            match = re.search(r"clubid=(\d+)", canonical.get("href", ""))
            if match:
                return match.group(1)

        # 방법 2: 스크립트에서 추출
        for script in soup.find_all("script"):
            text = script.string or ""
            match = re.search(r"['\"]?clubid['\"]?\s*[=:]\s*['\"]?(\d+)", text, re.I)
            if match:
                return match.group(1)

        # 방법 3: 리디렉트 URL에서 추출
        if resp.history:
            for r in resp.history:
                match = re.search(r"clubid=(\d+)", r.headers.get("Location", ""))
                if match:
                    return match.group(1)

        # 방법 4: 현재 URL에서 추출
        match = re.search(r"clubid=(\d+)", resp.url)
        if match:
            return match.group(1)

        raise CafeError(f"카페 ID를 찾을 수 없습니다: '{cafe_name}'. 카페 이름을 확인하세요.")

    def get_boards(self, cafe_name: str) -> list[dict]:
        """
        카페 게시판 목록 조회
        반환: [{"id": str, "name": str, "type": str}, ...]
        """
        cafe_id = self.get_cafe_id(cafe_name)
        self._cafe_id = cafe_id
        self._cafe_name = cafe_name

        # 카페 메인 페이지 로드 (iframe 내부)
        url = f"{config.NAVER_CAFE_BASE_URL}/ArticleList.nhn"
        params = {
            "search.clubid": cafe_id,
            "search.boardtype": "L",
        }
        resp = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        boards = []

        # 게시판 목록 파싱 (왼쪽 메뉴)
        # 카페 게시판은 menuId로 구분
        for link in soup.select("a[href*='search.menuid']"):
            href = link.get("href", "")
            match = re.search(r"search\.menuid=(\d+)", href)
            if not match:
                continue
            menu_id = match.group(1)
            board_name = link.get_text(strip=True)
            if not board_name:
                continue
            boards.append({
                "id": menu_id,
                "name": board_name,
                "url": f"{config.NAVER_CAFE_BASE_URL}/ArticleList.nhn"
                       f"?search.clubid={cafe_id}&search.menuid={menu_id}",
            })

        # 중복 제거
        seen = set()
        unique_boards = []
        for b in boards:
            key = (b["id"], b["name"])
            if key not in seen:
                seen.add(key)
                unique_boards.append(b)

        if not unique_boards:
            raise CafeError("게시판 목록을 불러올 수 없습니다. 카페 가입 여부를 확인하세요.")

        return unique_boards

    def get_post_list(
        self,
        cafe_id: str,
        menu_id: str,
        page: int = 1,
        per_page: int = 50,
    ) -> list[dict]:
        """
        특정 게시판의 게시글 목록 조회
        반환: [{"article_id": str, "title": str, "author": str, "date": str, "views": str}, ...]
        """
        url = f"{config.NAVER_CAFE_BASE_URL}/ArticleList.nhn"
        params = {
            "search.clubid": cafe_id,
            "search.menuid": menu_id,
            "search.page": page,
            "search.perPage": per_page,
            "search.boardtype": "L",
        }
        resp = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        posts = []

        # 게시글 목록 테이블 파싱
        for row in soup.select("table.article-board tbody tr"):
            # 공지, 광고 행 스킵
            if "notice" in row.get("class", []) or "ad" in row.get("class", []):
                continue

            title_cell = row.select_one("td.td_article a.article")
            if not title_cell:
                continue

            href = title_cell.get("href", "")
            match = re.search(r"articleid=(\d+)", href)
            article_id = match.group(1) if match else ""

            author_cell = row.select_one("td.td_name a, td.td_name em")
            date_cell = row.select_one("td.td_date")
            views_cell = row.select_one("td.td_view")
            comment_cell = row.select_one("span.cmt em, span.comment_count")

            posts.append({
                "article_id": article_id,
                "title": title_cell.get_text(strip=True),
                "author": author_cell.get_text(strip=True) if author_cell else "",
                "date": date_cell.get_text(strip=True) if date_cell else "",
                "views": views_cell.get_text(strip=True) if views_cell else "0",
                "comment_count": comment_cell.get_text(strip=True) if comment_cell else "0",
            })

        return posts

    def get_total_pages(self, cafe_id: str, menu_id: str, per_page: int = 50) -> int:
        """총 페이지 수 계산"""
        url = f"{config.NAVER_CAFE_BASE_URL}/ArticleList.nhn"
        params = {
            "search.clubid": cafe_id,
            "search.menuid": menu_id,
            "search.page": 1,
            "search.perPage": per_page,
            "search.boardtype": "L",
        }
        resp = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        # 페이지네이션에서 마지막 페이지 추출
        last_page_link = soup.select_one("a.pgR")  # 마지막 페이지 버튼
        if last_page_link:
            href = last_page_link.get("href", "")
            match = re.search(r"search\.page=(\d+)", href)
            if match:
                return int(match.group(1))

        # 번호로 된 페이지 링크 중 가장 큰 숫자
        page_nums = []
        for a in soup.select("a[href*='search.page']"):
            match = re.search(r"search\.page=(\d+)", a.get("href", ""))
            if match:
                page_nums.append(int(match.group(1)))

        return max(page_nums) if page_nums else 1
