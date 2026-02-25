"""
네이버 카페 게시글/댓글 파싱
게시글 목록에서 상세 내용 및 댓글 수집
"""
import time
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
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
from src.utils.date_utils import DateUtils
from config.settings import REQUEST_DELAY, exclude_keywords_manager

logger = logging.getLogger(__name__)


@dataclass
class Comment:
    """댓글 정보"""
    author: str
    content: str
    created_at: str
    is_reply: bool = False  # 대댓글 여부


@dataclass
class Post:
    """게시글 정보"""
    post_id: str
    title: str
    author: str
    created_at: str
    content: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    comments: List[Comment] = field(default_factory=list)
    url: str = ""


@dataclass
class PostListItem:
    """게시글 목록 항목 (상세 조회 전)"""
    post_id: str
    title: str
    author: str
    date_str: str
    url: str
    view_count: int = 0
    comment_count: int = 0


class PostParser:
    """게시글/댓글 파싱 클래스"""

    def __init__(
        self,
        driver: WebDriver,
        iframe_handler: IframeHandler,
        cafe_id: str,
        club_id: str = "",
        exclude_keywords: List[str] = None
    ):
        """
        Args:
            driver: Selenium WebDriver
            iframe_handler: iframe 전환 핸들러
            cafe_id: 카페 ID
            club_id: 카페 클럽 ID (숫자)
            exclude_keywords: 수집 제외 키워드 목록 (None이면 전역 설정 사용)
        """
        self.driver = driver
        self.iframe_handler = iframe_handler
        self.cafe_id = cafe_id
        self.club_id = club_id
        # 제외 키워드: 파라미터로 전달받거나 전역 설정 사용
        self.exclude_keywords = exclude_keywords if exclude_keywords is not None else exclude_keywords_manager.get_keywords()

    def _should_exclude(self, title: str, content: str = "") -> bool:
        """
        게시글이 제외 대상인지 확인

        Args:
            title: 게시글 제목
            content: 게시글 내용 (선택)

        Returns:
            제외 여부
        """
        if not self.exclude_keywords:
            return False

        text = f"{title} {content}".lower()
        for keyword in self.exclude_keywords:
            if keyword.lower() in text:
                logger.debug(f"제외 키워드 '{keyword}' 발견: {title[:30]}...")
                return True
        return False

    def get_post_list(
        self,
        board_id: str,
        max_pages: int = 5,
        max_posts: int = 100,
        today_only: bool = True
    ) -> List[PostListItem]:
        """
        게시판에서 게시글 목록 조회

        Args:
            board_id: 게시판 ID
            max_pages: 최대 조회 페이지 수
            max_posts: 최대 수집 게시글 수
            today_only: True면 오늘 작성된 글만

        Returns:
            게시글 목록 항목 리스트
        """
        posts = []
        page = 1

        while page <= max_pages and len(posts) < max_posts:
            logger.info(f"게시글 목록 {page}페이지 조회 중...")

            # 게시판 페이지로 이동
            board_url = self._build_board_url(board_id, page)
            self.driver.get(board_url)
            time.sleep(REQUEST_DELAY)

            # iframe 전환
            if not self.iframe_handler.switch_to_cafe_main():
                logger.error("iframe 전환 실패")
                break

            # 게시글 목록 파싱
            page_posts = self._parse_post_list_page()

            if not page_posts:
                logger.info("더 이상 게시글이 없습니다.")
                break

            if today_only:
                # 오늘 날짜만 필터링
                has_today_post = False
                for post in page_posts:
                    if len(posts) >= max_posts:
                        break
                    # 제외 키워드 체크
                    if self._should_exclude(post.title):
                        logger.info(f"제외 키워드로 인해 건너뜀: {post.title[:30]}...")
                        continue
                    if DateUtils.is_today(post.date_str):
                        posts.append(post)
                        has_today_post = True
                    else:
                        if has_today_post:
                            logger.info("오늘 날짜 게시글 수집 완료")
                            return posts

                if not has_today_post:
                    logger.info("오늘 작성된 글이 없습니다.")
                    break
            else:
                # 모든 게시글 수집
                for post in page_posts:
                    if len(posts) >= max_posts:
                        break
                    # 제외 키워드 체크
                    if self._should_exclude(post.title):
                        logger.info(f"제외 키워드로 인해 건너뜀: {post.title[:30]}...")
                        continue
                    posts.append(post)

                if len(posts) >= max_posts:
                    logger.info(f"최대 게시글 수({max_posts})에 도달")
                    break

            page += 1
            time.sleep(REQUEST_DELAY)

        return posts

    def _build_board_url(self, board_id: str, page: int = 1) -> str:
        """게시판 URL 구성"""
        club_id = self.club_id if self.club_id else "0"
        return (
            f"https://cafe.naver.com/{self.cafe_id}"
            f"?iframe_url_utf8=%2FArticleList.nhn"
            f"%3Fsearch.clubid%3D{club_id}"
            f"%26search.menuid%3D{board_id}"
            f"%26search.page%3D{page}"
        )

    def _parse_post_list_page(self) -> List[PostListItem]:
        """현재 페이지의 게시글 목록 파싱 - JavaScript 우선 사용"""
        # JavaScript로 파싱 (더 안정적)
        posts = self._parse_post_list_via_js()

        if posts:
            logger.debug(f"JavaScript 파싱으로 {len(posts)}개 게시글 발견")
            return posts

        # 실패시 셀렉터 방식 시도
        logger.debug("JavaScript 파싱 실패, 셀렉터 방식 시도")
        posts = []

        try:
            selectors = [
                "div.article-board tbody tr",
                ".board-list tbody tr",
                "#main-area table tbody tr",
            ]

            rows = []
            for selector in selectors:
                try:
                    rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if rows:
                        logger.debug(f"게시글 행 발견 (셀렉터: {selector}): {len(rows)}개")
                        break
                except:
                    continue

            for row in rows:
                try:
                    post = self._parse_post_row(row)
                    if post:
                        posts.append(post)
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    pass  # 조용히 무시

        except Exception as e:
            logger.error(f"게시글 목록 파싱 오류: {e}")

        return posts

    def _parse_post_row(self, row) -> Optional[PostListItem]:
        """개별 게시글 행 파싱"""
        try:
            # 공지사항 건너뛰기
            row_class = row.get_attribute("class") or ""
            if "notice" in row_class.lower():
                return None

            # 제목 및 링크
            title_elem = None
            title_selectors = [
                "td.td_article a.article",
                ".article a",
                "a.article-name",
                ".tit a"
            ]
            for sel in title_selectors:
                try:
                    title_elem = row.find_element(By.CSS_SELECTOR, sel)
                    if title_elem:
                        break
                except:
                    continue

            if not title_elem:
                return None

            title = title_elem.text.strip()
            href = title_elem.get_attribute("href") or ""

            # 게시글 ID 추출
            post_id = self._extract_post_id(href)
            if not post_id:
                return None

            # 작성자
            author = ""
            author_selectors = [
                "td.td_name a.m-tcol-c",
                ".nick a",
                ".author",
                "td.td_name"
            ]
            for sel in author_selectors:
                try:
                    author_elem = row.find_element(By.CSS_SELECTOR, sel)
                    author = author_elem.text.strip()
                    if author:
                        break
                except:
                    continue

            # 날짜
            date_str = ""
            date_selectors = ["td.td_date", ".date", ".time", "td:nth-child(4)"]
            for sel in date_selectors:
                try:
                    date_elem = row.find_element(By.CSS_SELECTOR, sel)
                    date_str = date_elem.text.strip()
                    if date_str:
                        break
                except:
                    continue

            # 조회수
            view_count = 0
            view_selectors = ["td.td_view", ".view", "td:nth-child(5)"]
            for sel in view_selectors:
                try:
                    view_elem = row.find_element(By.CSS_SELECTOR, sel)
                    view_text = view_elem.text.strip()
                    view_count = int(re.sub(r'[^\d]', '', view_text) or 0)
                    break
                except:
                    continue

            # 댓글 수
            comment_count = 0
            try:
                comment_elem = row.find_element(By.CSS_SELECTOR, ".comment-count, .reply-count, em.num")
                comment_text = comment_elem.text.strip()
                comment_count = int(re.sub(r'[^\d]', '', comment_text) or 0)
            except:
                pass

            # URL 구성
            if href.startswith("/"):
                url = f"https://cafe.naver.com{href}"
            else:
                url = href

            return PostListItem(
                post_id=post_id,
                title=title,
                author=author,
                date_str=date_str,
                url=url,
                view_count=view_count,
                comment_count=comment_count
            )

        except Exception as e:
            logger.debug(f"게시글 행 파싱 중 오류: {e}")
            return None

    def _extract_post_id(self, href: str) -> str:
        """URL에서 게시글 ID 추출"""
        if not href:
            return ""

        patterns = [
            r'articleid=(\d+)',
            r'ArticleRead\.nhn\?.*?articleid=(\d+)',
            r'/(\d+)(?:\?|$)',
        ]

        for pattern in patterns:
            match = re.search(pattern, href, re.IGNORECASE)
            if match:
                return match.group(1)

        return ""

    def _parse_post_list_via_js(self) -> List[PostListItem]:
        """JavaScript를 통한 게시글 목록 파싱"""
        posts = []

        try:
            script = """
            var posts = [];

            // 방법 1: article-board 테이블 행
            var rows = document.querySelectorAll('.article-board tbody tr');
            rows.forEach(function(row) {
                // 공지사항 건너뛰기
                if (row.classList.contains('notice')) return;

                // 제목 링크 찾기 (여러 셀렉터 시도)
                var titleLink = row.querySelector('a.article') ||
                               row.querySelector('td.td_article a') ||
                               row.querySelector('.inner a') ||
                               row.querySelector('a[href*="ArticleRead"]');

                if (!titleLink) return;

                var href = titleLink.getAttribute('href') || '';
                var title = titleLink.innerText.trim();

                // 작성자
                var authorElem = row.querySelector('.td_name a, .p-nick a, .nick, .author');
                var author = authorElem ? authorElem.innerText.trim() : '';

                // 날짜
                var dateElem = row.querySelector('.td_date, span.date, .date');
                var date = dateElem ? dateElem.innerText.trim() : '';

                // 조회수
                var viewElem = row.querySelector('.td_view, .view');
                var view = viewElem ? viewElem.innerText.trim() : '0';

                if (href && title) {
                    posts.push({
                        title: title,
                        href: href,
                        author: author,
                        date: date,
                        view: view
                    });
                }
            });

            // 방법 2: 링크 기반 파싱 (테이블이 없는 경우)
            if (posts.length === 0) {
                var links = document.querySelectorAll('a[href*="ArticleRead"]');
                links.forEach(function(link) {
                    var href = link.getAttribute('href');
                    var title = link.innerText.trim();
                    if (href && title && title.length > 2) {
                        posts.push({
                            title: title,
                            href: href,
                            author: '',
                            date: '',
                            view: '0'
                        });
                    }
                });
            }

            return posts;
            """

            result = self.driver.execute_script(script)
            logger.debug(f"JavaScript 파싱 결과: {len(result)}개")

            seen_ids = set()  # 중복 제거
            for item in result:
                href = item.get('href', '')
                post_id = self._extract_post_id(href)

                if post_id and post_id not in seen_ids:
                    seen_ids.add(post_id)
                    posts.append(PostListItem(
                        post_id=post_id,
                        title=item.get('title', ''),
                        author=item.get('author', ''),
                        date_str=item.get('date', ''),
                        url=href if href.startswith('http') else f"https://cafe.naver.com{href}",
                        view_count=int(re.sub(r'[^\d]', '', item.get('view', '0')) or 0)
                    ))

        except Exception as e:
            logger.error(f"JavaScript 게시글 목록 파싱 실패: {e}")

        return posts

    def get_post_detail(self, post_item: PostListItem) -> Post:
        """
        게시글 상세 정보 조회

        Args:
            post_item: 게시글 목록 항목

        Returns:
            상세 게시글 정보
        """
        logger.info(f"게시글 상세 조회: {post_item.title[:30]}...")

        try:
            # 게시글 페이지로 이동
            self.driver.get(post_item.url)
            time.sleep(REQUEST_DELAY)

            # iframe 전환
            if not self.iframe_handler.switch_to_cafe_main():
                logger.warning("iframe 전환 실패, 계속 진행")

            # 본문 내용 파싱
            content = self._parse_post_content()

            # 추가 정보 파싱 (조회수, 작성일 등)
            created_at = post_item.date_str
            view_count = post_item.view_count
            like_count = 0

            # 상세 페이지에서 정확한 정보 가져오기
            detail_info = self._parse_detail_info()
            if detail_info.get('created_at'):
                created_at = detail_info['created_at']
            if detail_info.get('view_count'):
                view_count = detail_info['view_count']
            if detail_info.get('like_count'):
                like_count = detail_info['like_count']

            # 댓글 파싱
            comments = self._parse_comments()

            return Post(
                post_id=post_item.post_id,
                title=post_item.title,
                author=post_item.author,
                created_at=created_at,
                content=content,
                view_count=view_count,
                like_count=like_count,
                comment_count=len(comments),
                comments=comments,
                url=post_item.url
            )

        except Exception as e:
            logger.error(f"게시글 상세 조회 실패: {e}")
            return Post(
                post_id=post_item.post_id,
                title=post_item.title,
                author=post_item.author,
                created_at=post_item.date_str,
                content="[파싱 실패]",
                url=post_item.url
            )

    def _parse_post_content(self) -> str:
        """게시글 본문 내용 파싱"""
        content = ""

        content_selectors = [
            "div.se-main-container",      # 새 에디터
            "div.ContentRenderer",        # 구 에디터
            ".article_viewer",
            "#postContent",
            ".post_content"
        ]

        for selector in content_selectors:
            try:
                content_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                content = content_elem.text.strip()
                if content:
                    break
            except:
                continue

        # JavaScript 대체 방법
        if not content:
            try:
                script = """
                var content = document.querySelector('.se-main-container, .ContentRenderer, .article_viewer');
                return content ? content.innerText.trim() : '';
                """
                content = self.driver.execute_script(script)
            except:
                pass

        return content

    def _parse_detail_info(self) -> Dict[str, Any]:
        """게시글 상세 정보 (작성일, 조회수 등) 파싱"""
        info = {}

        try:
            # 작성일
            date_selectors = [".date", ".article_info .date", ".post-date"]
            for sel in date_selectors:
                try:
                    date_elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                    info['created_at'] = date_elem.text.strip()
                    break
                except:
                    continue

            # 조회수
            view_selectors = [".count", ".article_info .view", ".hits"]
            for sel in view_selectors:
                try:
                    view_elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                    view_text = view_elem.text
                    info['view_count'] = int(re.sub(r'[^\d]', '', view_text) or 0)
                    break
                except:
                    continue

            # 좋아요 수
            like_selectors = [".like_count", ".u_cnt"]
            for sel in like_selectors:
                try:
                    like_elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                    like_text = like_elem.text
                    info['like_count'] = int(re.sub(r'[^\d]', '', like_text) or 0)
                    break
                except:
                    continue

        except Exception as e:
            logger.debug(f"상세 정보 파싱 오류: {e}")

        return info

    def _parse_comments(self) -> List[Comment]:
        """댓글 파싱 (더보기 처리 포함)"""
        comments = []

        try:
            # 댓글 더보기 버튼 클릭 (있을 경우)
            self._click_more_comments()

            # 댓글 컨테이너 찾기
            comment_selectors = [
                ".comment_list li",
                ".CommentItem",
                "#cmt_list li",
                ".comment_item"
            ]

            comment_elems = []
            for selector in comment_selectors:
                try:
                    comment_elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if comment_elems:
                        logger.debug(f"댓글 발견: {len(comment_elems)}개")
                        break
                except:
                    continue

            for elem in comment_elems:
                try:
                    comment = self._parse_single_comment(elem)
                    if comment:
                        comments.append(comment)
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    logger.debug(f"댓글 파싱 오류: {e}")
                    continue

        except Exception as e:
            logger.warning(f"댓글 파싱 중 오류: {e}")

        return comments

    def _click_more_comments(self, max_clicks: int = 10):
        """댓글 더보기 버튼 반복 클릭"""
        more_selectors = [
            ".btn_more",
            ".comment_more",
            "a.more_comment"
        ]

        clicks = 0
        while clicks < max_clicks:
            clicked = False

            for selector in more_selectors:
                try:
                    more_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if more_btn.is_displayed():
                        more_btn.click()
                        time.sleep(0.5)
                        clicked = True
                        clicks += 1
                        break
                except:
                    continue

            if not clicked:
                break

    def _parse_single_comment(self, elem) -> Optional[Comment]:
        """단일 댓글 파싱"""
        try:
            # 작성자
            author = ""
            author_selectors = [".comment_nickname", ".nick", ".author"]
            for sel in author_selectors:
                try:
                    author_elem = elem.find_element(By.CSS_SELECTOR, sel)
                    author = author_elem.text.strip()
                    if author:
                        break
                except:
                    continue

            # 내용
            content = ""
            content_selectors = [".text_comment", ".comment_text", ".content"]
            for sel in content_selectors:
                try:
                    content_elem = elem.find_element(By.CSS_SELECTOR, sel)
                    content = content_elem.text.strip()
                    if content:
                        break
                except:
                    continue

            # 작성 시간
            created_at = ""
            time_selectors = [".comment_info_date", ".date", ".time"]
            for sel in time_selectors:
                try:
                    time_elem = elem.find_element(By.CSS_SELECTOR, sel)
                    created_at = time_elem.text.strip()
                    if created_at:
                        break
                except:
                    continue

            # 대댓글 여부
            is_reply = "reply" in (elem.get_attribute("class") or "").lower()

            if author or content:
                return Comment(
                    author=author,
                    content=content,
                    created_at=created_at,
                    is_reply=is_reply
                )

        except Exception as e:
            logger.debug(f"단일 댓글 파싱 오류: {e}")

        return None

    def crawl_today_posts(self, board_id: str) -> List[Post]:
        """오늘 게시글 전체 크롤링 (하위 호환성)"""
        return self.crawl_posts(board_id, today_only=True)

    def crawl_posts(
        self,
        board_id: str,
        max_posts: int = 20,
        max_pages: int = 1,
        today_only: bool = False
    ) -> List[Post]:
        """
        게시글 크롤링 (목록 + 상세 + 댓글)

        Args:
            board_id: 게시판 ID
            max_posts: 최대 수집 게시글 수
            max_pages: 최대 조회 페이지 수
            today_only: True면 오늘 작성된 글만

        Returns:
            완전한 게시글 리스트 (댓글 포함)
        """
        # 게시글 목록 조회
        post_list = self.get_post_list(
            board_id,
            max_pages=max_pages,
            max_posts=max_posts,
            today_only=today_only
        )

        if today_only:
            logger.info(f"오늘 작성된 게시글: {len(post_list)}개")
        else:
            logger.info(f"수집된 게시글 목록: {len(post_list)}개")

        if not post_list:
            return []

        # 각 게시글 상세 조회
        posts = []
        for idx, item in enumerate(post_list, 1):
            logger.info(f"게시글 상세 조회 중 ({idx}/{len(post_list)}): {item.title[:30]}...")

            post = self.get_post_detail(item)
            posts.append(post)

            # 요청 간격 조절
            if idx < len(post_list):
                time.sleep(REQUEST_DELAY)

        return posts
