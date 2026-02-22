"""
게시글 및 댓글 크롤러
- 개별 게시글 본문 크롤링
- 댓글(일반 댓글 + 대댓글) 크롤링
- 전체 게시판 순차 크롤링
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from typing import Optional
from datetime import datetime

import config
from cafe_manager import CafeManager


class PostCrawler:
    def __init__(self, session: requests.Session, cafe_id: str, cafe_name: str):
        self.session = session
        self.cafe_id = cafe_id
        self.cafe_name = cafe_name

    def get_post_content(self, article_id: str) -> dict:
        """
        게시글 본문 크롤링
        반환: {
            "article_id": str,
            "title": str,
            "author": str,
            "date": str,
            "content": str,
            "views": str,
            "likes": str,
            "url": str,
        }
        """
        url = f"{config.NAVER_CAFE_BASE_URL}/ArticleRead.nhn"
        params = {
            "clubid": self.cafe_id,
            "articleid": article_id,
        }

        # 카페 게시글은 iframe 안에 있어 직접 접근 필요
        article_url = (
            f"https://cafe.naver.com/{self.cafe_name}/{article_id}"
        )

        self.session.headers.update({
            "Referer": f"{config.NAVER_CAFE_BASE_URL}/{self.cafe_name}",
        })

        resp = self.session.get(article_url, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        # iframe 내부 URL 추출 (카페 글은 iframe 구조)
        iframe = soup.find("iframe", id="cafe_main")
        if iframe:
            iframe_src = iframe.get("src", "")
            if iframe_src:
                if not iframe_src.startswith("http"):
                    iframe_src = config.NAVER_CAFE_BASE_URL + iframe_src
                self.session.headers.update({"Referer": article_url})
                resp = self.session.get(iframe_src, timeout=config.REQUEST_TIMEOUT)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")

        # 제목 추출
        title = ""
        for sel in [".tit-box .title", "h3.title", ".article-head .title", "h1.title_text"]:
            elem = soup.select_one(sel)
            if elem:
                title = elem.get_text(strip=True)
                break

        # 작성자 추출
        author = ""
        for sel in [".nick-box .m-tcol-c", ".article_writer .p-nick", ".writer_info .user_nick"]:
            elem = soup.select_one(sel)
            if elem:
                author = elem.get_text(strip=True)
                break

        # 날짜 추출
        date = ""
        for sel in [".date", ".article_info .date", "span.date"]:
            elem = soup.select_one(sel)
            if elem:
                date = elem.get_text(strip=True)
                break

        # 본문 추출
        content = ""
        for sel in [".article-viewer", "#tbody", ".ContentRenderer", ".se-main-container"]:
            elem = soup.select_one(sel)
            if elem:
                # 이미지 alt 텍스트 보존, 불필요한 태그 제거
                content = elem.get_text(separator="\n", strip=True)
                break

        # 조회수, 좋아요 추출
        views = ""
        likes = ""
        for sel in [".article_info .count", ".view_count"]:
            elem = soup.select_one(sel)
            if elem:
                views = elem.get_text(strip=True)
                break
        for sel in [".like_count", ".article_like .count"]:
            elem = soup.select_one(sel)
            if elem:
                likes = elem.get_text(strip=True)
                break

        return {
            "article_id": article_id,
            "title": title,
            "author": author,
            "date": date,
            "content": content,
            "views": views,
            "likes": likes,
            "url": f"https://cafe.naver.com/{self.cafe_name}/{article_id}",
            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_comments(self, article_id: str) -> list[dict]:
        """
        게시글의 댓글 + 대댓글 크롤링 (API 방식)
        반환: [{
            "comment_id": str,
            "parent_id": str,      # 대댓글인 경우 부모 댓글 ID
            "author": str,
            "content": str,
            "date": str,
            "is_reply": bool,
        }, ...]
        """
        # 네이버 카페 댓글 API
        api_url = "https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{}/articles/{}/comments".format(
            self.cafe_id, article_id
        )

        params = {
            "requestFrom": "A",
            "page": 1,
            "pageSize": 100,
        }

        self.session.headers.update({
            "Referer": f"https://cafe.naver.com/{self.cafe_name}/{article_id}",
        })

        all_comments = []
        page = 1

        while True:
            params["page"] = page
            try:
                resp = self.session.get(
                    api_url,
                    params=params,
                    timeout=config.REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                # API 실패 시 HTML 파싱으로 폴백
                all_comments.extend(self._get_comments_from_html(article_id))
                break

            result = data.get("result", {})
            comment_list = result.get("comments", {}).get("items", [])

            if not comment_list:
                break

            for c in comment_list:
                comment = {
                    "comment_id": str(c.get("id", "")),
                    "parent_id": str(c.get("parentId", "")) if c.get("parentId") else "",
                    "author": c.get("writer", {}).get("nick", ""),
                    "content": c.get("content", ""),
                    "date": c.get("writeDate", ""),
                    "is_reply": bool(c.get("parentId")),
                }
                all_comments.append(comment)

                # 대댓글 처리
                for reply in c.get("replies", {}).get("items", []):
                    all_comments.append({
                        "comment_id": str(reply.get("id", "")),
                        "parent_id": str(c.get("id", "")),
                        "author": reply.get("writer", {}).get("nick", ""),
                        "content": reply.get("content", ""),
                        "date": reply.get("writeDate", ""),
                        "is_reply": True,
                    })

            total_count = result.get("comments", {}).get("totalCount", 0)
            if len(all_comments) >= total_count:
                break
            page += 1
            time.sleep(config.CRAWL_DELAY)

        return all_comments

    def _get_comments_from_html(self, article_id: str) -> list[dict]:
        """HTML에서 댓글 파싱 (API 실패 시 폴백)"""
        url = f"{config.NAVER_CAFE_BASE_URL}/ArticleRead.nhn"
        params = {"clubid": self.cafe_id, "articleid": article_id}

        resp = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        comments = []
        for idx, cmt in enumerate(soup.select(".comment_area .comment_box")):
            author_el = cmt.select_one(".comment_writer_id, .nick")
            content_el = cmt.select_one(".comment_text_box span")
            date_el = cmt.select_one(".comment_info_date")

            comments.append({
                "comment_id": f"cmt_{idx}",
                "parent_id": "",
                "author": author_el.get_text(strip=True) if author_el else "",
                "content": content_el.get_text(strip=True) if content_el else "",
                "date": date_el.get_text(strip=True) if date_el else "",
                "is_reply": "reply" in cmt.get("class", []),
            })
        return comments


class BoardCrawler:
    """
    게시판 전체 크롤링 오케스트레이터
    - 게시판 내 모든 게시글을 순차적으로 크롤링
    - 진행 상황 콜백 지원
    """

    def __init__(self, session: requests.Session, cafe_id: str, cafe_name: str):
        self.session = session
        self.cafe_id = cafe_id
        self.cafe_name = cafe_name
        self.cafe_manager = CafeManager(session)
        self.post_crawler = PostCrawler(session, cafe_id, cafe_name)

    def crawl_board(
        self,
        menu_id: str,
        max_pages: Optional[int] = None,
        include_comments: bool = True,
        progress_callback=None,
    ) -> tuple[list[dict], list[dict]]:
        """
        게시판 크롤링 실행
        Args:
            menu_id: 게시판 ID
            max_pages: 최대 크롤링 페이지 수 (None=전체)
            include_comments: 댓글 크롤링 여부
            progress_callback: 진행 상황 콜백 fn(current, total, msg)
        Returns:
            (posts_data, comments_data)
        """
        # 총 페이지 수 확인
        total_pages = self.cafe_manager.get_total_pages(self.cafe_id, menu_id)
        if max_pages:
            total_pages = min(total_pages, max_pages)

        all_posts = []
        all_comments = []
        total_crawled = 0

        for page in range(1, total_pages + 1):
            msg = f"페이지 {page}/{total_pages} 게시글 목록 조회 중..."
            if progress_callback:
                progress_callback(page, total_pages, msg)
            else:
                print(f"  {msg}")

            # 게시글 목록 가져오기
            post_list = self.cafe_manager.get_post_list(self.cafe_id, menu_id, page)
            time.sleep(config.CRAWL_DELAY)

            for post_meta in post_list:
                article_id = post_meta["article_id"]
                if not article_id:
                    continue

                print(f"    [게시글] {post_meta['title'][:40]}...")

                try:
                    # 게시글 본문 크롤링
                    post_data = self.post_crawler.get_post_content(article_id)
                    post_data.update({
                        "board_id": menu_id,
                        "comment_count": post_meta.get("comment_count", "0"),
                    })
                    all_posts.append(post_data)
                    time.sleep(config.CRAWL_DELAY)

                    # 댓글 크롤링
                    if include_comments:
                        comments = self.post_crawler.get_comments(article_id)
                        for c in comments:
                            c["article_id"] = article_id
                            c["board_id"] = menu_id
                        all_comments.extend(comments)
                        time.sleep(config.CRAWL_DELAY)

                    total_crawled += 1
                    if total_crawled >= config.MAX_POSTS_PER_RUN:
                        print(f"  최대 크롤링 수({config.MAX_POSTS_PER_RUN}개)에 도달했습니다.")
                        return all_posts, all_comments

                except Exception as e:
                    print(f"    [오류] 게시글 {article_id} 크롤링 실패: {e}")
                    continue

        return all_posts, all_comments
