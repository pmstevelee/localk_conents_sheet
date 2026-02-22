"""
CSV 내보내기 모듈
- 게시글과 댓글을 별도 CSV 파일로 저장
- 날짜별 파일명 자동 생성
- 기존 파일에 추가(append) 또는 덮어쓰기 선택 가능
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

import config


# CSV 컬럼 정의
POST_COLUMNS = [
    "article_id",
    "board_id",
    "title",
    "author",
    "date",
    "content",
    "views",
    "likes",
    "comment_count",
    "url",
    "crawled_at",
]

COMMENT_COLUMNS = [
    "comment_id",
    "article_id",
    "board_id",
    "parent_id",
    "author",
    "content",
    "date",
    "is_reply",
]


class CSVExporter:
    def __init__(self, cafe_name: str, output_dir: Optional[Path] = None):
        self.cafe_name = cafe_name
        self.output_dir = output_dir or config.ensure_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_filename(self, data_type: str, date_str: Optional[str] = None) -> Path:
        """
        출력 파일명 생성
        형식: {cafe_name}_{data_type}_{YYYY-MM-DD}.csv
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{self.cafe_name}_{data_type}_{date_str}.csv"
        return self.output_dir / filename

    def save_posts(
        self,
        posts: list[dict],
        date_str: Optional[str] = None,
        append: bool = True,
    ) -> Path:
        """
        게시글 CSV 저장
        Args:
            posts: 게시글 데이터 리스트
            date_str: 날짜 문자열 (None이면 오늘 날짜)
            append: True면 기존 파일에 추가, False면 덮어쓰기
        Returns:
            저장된 파일 경로
        """
        filepath = self._get_filename("posts", date_str)
        mode = "a" if (append and filepath.exists()) else "w"
        write_header = not (append and filepath.exists())

        with open(filepath, mode, encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=POST_COLUMNS,
                extrasaction="ignore",
                quoting=csv.QUOTE_ALL,
            )
            if write_header:
                writer.writeheader()

            for post in posts:
                # 줄바꿈 정리
                if "content" in post:
                    post["content"] = post["content"].replace("\n", " | ").strip()
                writer.writerow({col: post.get(col, "") for col in POST_COLUMNS})

        return filepath

    def save_comments(
        self,
        comments: list[dict],
        date_str: Optional[str] = None,
        append: bool = True,
    ) -> Path:
        """
        댓글 CSV 저장
        Args:
            comments: 댓글 데이터 리스트
            date_str: 날짜 문자열
            append: True면 기존 파일에 추가
        Returns:
            저장된 파일 경로
        """
        filepath = self._get_filename("comments", date_str)
        mode = "a" if (append and filepath.exists()) else "w"
        write_header = not (append and filepath.exists())

        with open(filepath, mode, encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=COMMENT_COLUMNS,
                extrasaction="ignore",
                quoting=csv.QUOTE_ALL,
            )
            if write_header:
                writer.writeheader()

            for comment in comments:
                if "content" in comment:
                    comment["content"] = comment["content"].replace("\n", " ").strip()
                writer.writerow({col: comment.get(col, "") for col in COMMENT_COLUMNS})

        return filepath

    def save_all(
        self,
        posts: list[dict],
        comments: list[dict],
        date_str: Optional[str] = None,
        append: bool = True,
    ) -> tuple[Path, Path]:
        """게시글 + 댓글 한 번에 저장"""
        posts_path = self.save_posts(posts, date_str, append)
        comments_path = self.save_comments(comments, date_str, append)
        return posts_path, comments_path

    def get_stats(self, posts: list[dict], comments: list[dict]) -> dict:
        """크롤링 통계 반환"""
        return {
            "total_posts": len(posts),
            "total_comments": len(comments),
            "total_replies": sum(1 for c in comments if c.get("is_reply")),
            "crawled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def print_stats(self, posts: list[dict], comments: list[dict],
                    posts_path: Path, comments_path: Path) -> None:
        """크롤링 결과 출력"""
        stats = self.get_stats(posts, comments)
        print("\n" + "=" * 50)
        print("크롤링 완료!")
        print(f"  게시글: {stats['total_posts']}개")
        print(f"  댓글:   {stats['total_comments']}개 (대댓글 {stats['total_replies']}개 포함)")
        print(f"  저장 위치:")
        print(f"    게시글 → {posts_path}")
        print(f"    댓글   → {comments_path}")
        print("=" * 50)
