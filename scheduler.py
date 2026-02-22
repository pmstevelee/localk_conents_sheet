"""
매일 자동 크롤링 스케줄러
- schedule 라이브러리 기반 일일 작업 등록
- 사용자 지정 시간에 크롤링 자동 실행
- 실행 로그 저장
"""

import time
import logging
import schedule
from datetime import datetime
from pathlib import Path
from typing import Callable

import config

# 로그 설정
LOG_FILE = Path(__file__).parent / "crawler.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class CrawlScheduler:
    def __init__(self, crawl_func: Callable, run_time: str = config.DEFAULT_SCHEDULE_TIME):
        """
        Args:
            crawl_func: 매일 실행할 크롤링 함수 (인자 없음)
            run_time: 실행 시간 "HH:MM" 형식 (예: "09:00")
        """
        self.crawl_func = crawl_func
        self.run_time = run_time
        self._scheduled = False

    def _run_job(self) -> None:
        """크롤링 작업 실행 (예외 처리 포함)"""
        logger.info(f"자동 크롤링 시작 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        try:
            self.crawl_func()
            logger.info("자동 크롤링 완료")
        except Exception as e:
            logger.error(f"자동 크롤링 실패: {e}", exc_info=True)

    def start(self, run_immediately: bool = False) -> None:
        """
        스케줄러 시작
        Args:
            run_immediately: True면 스케줄 등록 즉시 1회 실행
        """
        # 기존 스케줄 초기화
        schedule.clear()

        # 매일 지정 시간에 실행 등록
        schedule.every().day.at(self.run_time).do(self._run_job)
        self._scheduled = True

        logger.info(f"스케줄러 등록: 매일 {self.run_time}에 크롤링 실행")

        if run_immediately:
            logger.info("즉시 1회 실행...")
            self._run_job()

        print(f"\n스케줄러가 시작되었습니다. 매일 {self.run_time}에 자동 크롤링됩니다.")
        print("중지하려면 Ctrl+C 를 누르세요.\n")

        try:
            while True:
                schedule.run_pending()
                time.sleep(30)  # 30초마다 스케줄 확인
        except KeyboardInterrupt:
            logger.info("스케줄러 중지됨 (사용자 요청)")
            print("\n스케줄러가 중지되었습니다.")

    def stop(self) -> None:
        """스케줄 취소"""
        schedule.clear()
        self._scheduled = False
        logger.info("스케줄러 중지")

    @property
    def next_run(self) -> str:
        """다음 실행 예정 시간 문자열"""
        job = schedule.next_run()
        if job:
            return job.strftime("%Y-%m-%d %H:%M:%S")
        return "예정 없음"

    @staticmethod
    def run_once(crawl_func: Callable) -> None:
        """스케줄 없이 1회만 즉시 실행"""
        logger.info("1회 즉시 크롤링 실행")
        try:
            crawl_func()
            logger.info("크롤링 완료")
        except Exception as e:
            logger.error(f"크롤링 실패: {e}", exc_info=True)
            raise
