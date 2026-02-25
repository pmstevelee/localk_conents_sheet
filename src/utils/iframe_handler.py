"""
네이버 카페 iframe 처리 유틸리티
네이버 카페는 콘텐츠가 iframe 안에 있어 별도 처리 필요
"""
import time
import logging
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchFrameException,
    StaleElementReferenceException
)

logger = logging.getLogger(__name__)


class IframeHandler:
    """네이버 카페 iframe 전환 관리"""

    # 네이버 카페 메인 iframe ID
    CAFE_MAIN_FRAME_ID = "cafe_main"

    def __init__(self, driver: WebDriver, timeout: int = 10):
        """
        Args:
            driver: Selenium WebDriver 인스턴스
            timeout: 대기 타임아웃 (초)
        """
        self.driver = driver
        self.timeout = timeout
        self._is_in_iframe = False

    def switch_to_cafe_main(self) -> bool:
        """
        카페 메인 iframe으로 전환

        Returns:
            전환 성공 여부
        """
        try:
            # 이미 iframe 안에 있으면 먼저 나가기
            if self._is_in_iframe:
                self.switch_to_default()

            # iframe 로딩 대기
            WebDriverWait(self.driver, self.timeout).until(
                EC.frame_to_be_available_and_switch_to_it(
                    (By.ID, self.CAFE_MAIN_FRAME_ID)
                )
            )

            self._is_in_iframe = True
            logger.debug("카페 메인 iframe으로 전환 완료")
            return True

        except TimeoutException:
            logger.error(f"iframe 전환 타임아웃: {self.CAFE_MAIN_FRAME_ID}")
            return False
        except NoSuchFrameException:
            logger.error(f"iframe을 찾을 수 없음: {self.CAFE_MAIN_FRAME_ID}")
            return False
        except Exception as e:
            logger.error(f"iframe 전환 중 오류: {e}")
            return False

    def switch_to_default(self):
        """기본 컨텍스트(최상위)로 복귀"""
        try:
            self.driver.switch_to.default_content()
            self._is_in_iframe = False
            logger.debug("기본 컨텍스트로 복귀")
        except Exception as e:
            logger.warning(f"기본 컨텍스트 복귀 중 오류: {e}")

    def refresh_iframe(self, wait_time: float = 1.0) -> bool:
        """
        페이지 이동 후 iframe 재전환

        네이버 카페에서 링크 클릭 후 새 페이지가 iframe 안에 로드될 때 사용

        Args:
            wait_time: 페이지 로딩 대기 시간 (초)

        Returns:
            재전환 성공 여부
        """
        self.switch_to_default()
        time.sleep(wait_time)
        return self.switch_to_cafe_main()

    def wait_for_element_in_iframe(
        self,
        by: By,
        value: str,
        timeout: int = None
    ):
        """
        iframe 내부 요소 대기

        Args:
            by: 검색 방법 (By.ID, By.CSS_SELECTOR 등)
            value: 검색 값
            timeout: 대기 시간 (None이면 기본값 사용)

        Returns:
            찾은 요소 또는 None
        """
        if timeout is None:
            timeout = self.timeout

        try:
            # iframe 안에 있는지 확인
            if not self._is_in_iframe:
                self.switch_to_cafe_main()

            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element

        except TimeoutException:
            logger.warning(f"요소 대기 타임아웃: {by}={value}")
            return None
        except StaleElementReferenceException:
            # 요소가 stale해진 경우 iframe 재전환 후 재시도
            logger.debug("Stale element - iframe 재전환 시도")
            if self.refresh_iframe():
                try:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((by, value))
                    )
                    return element
                except:
                    pass
            return None

    @property
    def is_in_iframe(self) -> bool:
        """현재 iframe 내부에 있는지 여부"""
        return self._is_in_iframe
