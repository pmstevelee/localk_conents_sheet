"""
CSV 저장 처리
크롤링된 게시글/댓글을 CSV 파일로 저장
"""
import csv
import os
import re
import logging
from datetime import datetime
from typing import List
from pathlib import Path

import sys
sys.path.append(str(__file__).rsplit('/', 3)[0])
from src.crawler.post_parser import Post, Comment
from config.settings import OUTPUT_DIR

logger = logging.getLogger(__name__)


class CSVHandler:
    """CSV 파일 저장 클래스"""

    # CSV 헤더
    HEADERS = [
        '게시글ID',
        '제목',
        '작성자',
        '작성일',
        '조회수',
        '좋아요수',
        '본문내용',
        '댓글작성자',
        '댓글내용',
        '댓글작성일',
        '대댓글여부',
        'URL'
    ]

    def __init__(self, output_dir: str = None):
        """
        Args:
            output_dir: 출력 디렉토리 경로 (None이면 기본 경로 사용)
        """
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, name: str) -> str:
        """파일명에 사용할 수 없는 문자 제거"""
        # 파일명에 부적합한 문자 제거
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        # 공백을 언더스코어로
        sanitized = sanitized.replace(' ', '_')
        # 연속된 언더스코어 정리
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized.strip('_')

    def save_posts(
        self,
        posts: List[Post],
        cafe_name: str,
        board_name: str,
        filename: str = None
    ) -> str:
        """
        게시글 목록을 CSV 파일로 저장

        게시글당 댓글 수만큼 행이 생성됨 (댓글 펼침 형식)
        댓글이 없는 게시글은 빈 댓글 컬럼으로 1행 생성

        Args:
            posts: 저장할 게시글 목록
            cafe_name: 카페 이름/ID
            board_name: 게시판 이름
            filename: 파일명 (None이면 자동 생성)

        Returns:
            저장된 파일 경로
        """
        if not posts:
            logger.warning("저장할 게시글이 없습니다.")
            return ""

        # 파일명 생성
        if not filename:
            today = datetime.now().strftime("%Y%m%d")
            safe_cafe = self._sanitize_filename(cafe_name)
            safe_board = self._sanitize_filename(board_name)
            filename = f"{safe_cafe}_{safe_board}_{today}.csv"

        filepath = self.output_dir / filename

        try:
            # CSV 파일 쓰기
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)

                # 헤더 쓰기
                writer.writerow(self.HEADERS)

                # 데이터 쓰기
                row_count = 0
                for post in posts:
                    rows = self._post_to_rows(post)
                    for row in rows:
                        writer.writerow(row)
                        row_count += 1

            logger.info(f"CSV 저장 완료: {filepath} ({len(posts)}개 게시글, {row_count}개 행)")
            return str(filepath)

        except Exception as e:
            logger.error(f"CSV 저장 실패: {e}")
            raise

    def _post_to_rows(self, post: Post) -> List[List[str]]:
        """
        게시글을 CSV 행들로 변환

        Args:
            post: 게시글 객체

        Returns:
            CSV 행 리스트
        """
        rows = []

        # 본문 내용 정리 (줄바꿈을 공백으로)
        content = post.content.replace('\n', ' ').replace('\r', '').strip()

        base_row = [
            post.post_id,
            post.title,
            post.author,
            post.created_at,
            str(post.view_count),
            str(post.like_count),
            content
        ]

        if post.comments:
            # 댓글이 있는 경우: 각 댓글마다 행 생성
            for comment in post.comments:
                comment_content = comment.content.replace('\n', ' ').replace('\r', '').strip()
                row = base_row + [
                    comment.author,
                    comment_content,
                    comment.created_at,
                    '대댓글' if comment.is_reply else '댓글',
                    post.url
                ]
                rows.append(row)
        else:
            # 댓글이 없는 경우: 빈 댓글로 1행 생성
            row = base_row + ['', '', '', '', post.url]
            rows.append(row)

        return rows

    def save_posts_compact(
        self,
        posts: List[Post],
        cafe_name: str,
        board_name: str,
        filename: str = None
    ) -> str:
        """
        게시글을 컴팩트 형식으로 저장 (게시글당 1행, 댓글은 JSON)

        Args:
            posts: 저장할 게시글 목록
            cafe_name: 카페 이름/ID
            board_name: 게시판 이름
            filename: 파일명 (None이면 자동 생성)

        Returns:
            저장된 파일 경로
        """
        import json

        if not posts:
            logger.warning("저장할 게시글이 없습니다.")
            return ""

        # 파일명 생성
        if not filename:
            today = datetime.now().strftime("%Y%m%d")
            safe_cafe = self._sanitize_filename(cafe_name)
            safe_board = self._sanitize_filename(board_name)
            filename = f"{safe_cafe}_{safe_board}_{today}_compact.csv"

        filepath = self.output_dir / filename

        compact_headers = [
            '게시글ID',
            '제목',
            '작성자',
            '작성일',
            '조회수',
            '좋아요수',
            '댓글수',
            '본문내용',
            '댓글(JSON)',
            'URL'
        ]

        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(compact_headers)

                for post in posts:
                    content = post.content.replace('\n', ' ').replace('\r', '').strip()

                    # 댓글을 JSON으로 변환
                    comments_json = json.dumps([
                        {
                            'author': c.author,
                            'content': c.content,
                            'date': c.created_at,
                            'is_reply': c.is_reply
                        }
                        for c in post.comments
                    ], ensure_ascii=False)

                    row = [
                        post.post_id,
                        post.title,
                        post.author,
                        post.created_at,
                        str(post.view_count),
                        str(post.like_count),
                        str(post.comment_count),
                        content,
                        comments_json,
                        post.url
                    ]
                    writer.writerow(row)

            logger.info(f"컴팩트 CSV 저장 완료: {filepath} ({len(posts)}개 게시글)")
            return str(filepath)

        except Exception as e:
            logger.error(f"컴팩트 CSV 저장 실패: {e}")
            raise

    def get_existing_post_ids(self, filepath: str) -> set:
        """
        기존 CSV 파일에서 게시글 ID 목록 추출 (중복 방지용)

        Args:
            filepath: CSV 파일 경로

        Returns:
            게시글 ID 집합
        """
        post_ids = set()

        if not os.path.exists(filepath):
            return post_ids

        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader)  # 헤더 스킵

                for row in reader:
                    if row:
                        post_ids.add(row[0])

        except Exception as e:
            logger.warning(f"기존 파일 읽기 실패: {e}")

        return post_ids

    def append_posts(
        self,
        posts: List[Post],
        filepath: str
    ) -> int:
        """
        기존 CSV 파일에 게시글 추가 (중복 제외)

        Args:
            posts: 추가할 게시글 목록
            filepath: 기존 CSV 파일 경로

        Returns:
            추가된 게시글 수
        """
        existing_ids = self.get_existing_post_ids(filepath)
        new_posts = [p for p in posts if p.post_id not in existing_ids]

        if not new_posts:
            logger.info("추가할 새 게시글이 없습니다.")
            return 0

        try:
            with open(filepath, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)

                row_count = 0
                for post in new_posts:
                    rows = self._post_to_rows(post)
                    for row in rows:
                        writer.writerow(row)
                        row_count += 1

            logger.info(f"{len(new_posts)}개 게시글 추가 완료 ({row_count}개 행)")
            return len(new_posts)

        except Exception as e:
            logger.error(f"게시글 추가 실패: {e}")
            return 0
