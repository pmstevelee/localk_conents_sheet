"""
날짜 관련 유틸리티
오늘 날짜 게시글 필터링용
"""
import re
from datetime import datetime, date, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DateUtils:
    """날짜 처리 유틸리티"""

    @staticmethod
    def is_today(date_str: str) -> bool:
        """
        날짜 문자열이 오늘인지 확인

        지원 형식:
        - "2026.02.23", "2026-02-23" (전체 날짜)
        - "02.23.", "02.23" (월.일)
        - "23:45" (시간만 - 오늘 작성)
        - "1분 전", "30분 전", "1시간 전" (상대 시간)
        - "방금" (방금 전)

        Args:
            date_str: 날짜 문자열

        Returns:
            오늘 날짜이면 True
        """
        if not date_str:
            return False

        date_str = date_str.strip()
        today = date.today()

        # 시간만 표시된 경우 (예: "23:45") - 오늘 작성
        if re.match(r'^\d{1,2}:\d{2}$', date_str):
            return True

        # 상대 시간 형식 (예: "1분 전", "30분 전", "1시간 전", "방금")
        if '분 전' in date_str or '시간 전' in date_str or date_str == '방금':
            return True

        # "n일 전" 형식
        day_match = re.match(r'(\d+)일 전', date_str)
        if day_match:
            days_ago = int(day_match.group(1))
            return days_ago == 0

        # 전체 날짜 형식 (예: "2026.02.23", "2026-02-23")
        full_date_match = re.match(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', date_str)
        if full_date_match:
            year, month, day = map(int, full_date_match.groups())
            return date(year, month, day) == today

        # 월.일 형식 (예: "02.23.", "02.23", "2.23")
        short_date_match = re.match(r'(\d{1,2})[.\-/](\d{1,2})\.?$', date_str)
        if short_date_match:
            month, day = map(int, short_date_match.groups())
            return month == today.month and day == today.day

        logger.debug(f"인식되지 않은 날짜 형식: {date_str}")
        return False

    @staticmethod
    def parse_date(date_str: str) -> Optional[date]:
        """
        날짜 문자열을 date 객체로 변환

        Args:
            date_str: 날짜 문자열

        Returns:
            date 객체 또는 None
        """
        if not date_str:
            return None

        date_str = date_str.strip()
        today = date.today()

        # 시간만/상대시간 - 오늘
        if re.match(r'^\d{1,2}:\d{2}$', date_str):
            return today
        if '분 전' in date_str or '시간 전' in date_str or date_str == '방금':
            return today

        # "n일 전"
        day_match = re.match(r'(\d+)일 전', date_str)
        if day_match:
            days_ago = int(day_match.group(1))
            return today - timedelta(days=days_ago)

        # 전체 날짜
        full_date_match = re.match(r'(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})', date_str)
        if full_date_match:
            year, month, day = map(int, full_date_match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                return None

        # 월.일 (올해로 가정)
        short_date_match = re.match(r'(\d{1,2})[.\-/](\d{1,2})\.?$', date_str)
        if short_date_match:
            month, day = map(int, short_date_match.groups())
            try:
                return date(today.year, month, day)
            except ValueError:
                return None

        return None

    @staticmethod
    def get_today_string(format_type: str = "dot") -> str:
        """
        오늘 날짜를 문자열로 반환

        Args:
            format_type: "dot" (2026.02.23), "dash" (2026-02-23), "compact" (20260223)

        Returns:
            포맷된 날짜 문자열
        """
        today = date.today()

        if format_type == "dot":
            return today.strftime("%Y.%m.%d")
        elif format_type == "dash":
            return today.strftime("%Y-%m-%d")
        elif format_type == "compact":
            return today.strftime("%Y%m%d")
        else:
            return today.strftime("%Y.%m.%d")
