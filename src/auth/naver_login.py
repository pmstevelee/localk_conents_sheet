"""
네이버 로그인 처리
봇 탐지 우회를 위한 클립보드 붙여넣기 방식 사용
"""
import time
import logging
import platform
import pyperclip
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import sys
sys.path.append(str(__file__).rsplit('/', 3)[0])
from config.settings import NAVER_LOGIN_URL

logger = logging.getLogger(__name__)


class NaverLoginError(Exception):
    """네이버 로그인 관련 예외"""
    pass


class CaptchaDetectedError(NaverLoginError):
    """캡차 감지 예외"""
    pass


class NaverLogin:
    """네이버 로그인 처리 클래스"""

    # 로그인 폼 셀렉터
    ID_INPUT_SELECTOR = "#id"
    PW_INPUT_SELECTOR = "#pw"
    LOGIN_BUTTON_SELECTOR = "#log\\.login"

    # 로그인 성공/실패 확인용
    LOGIN_ERROR_SELECTOR = "#err_common"
    CAPTCHA_SELECTOR = "#captcha"

    def __init__(self, driver: WebDriver, timeout: int = 10, manual_mode: bool = False):
        """
        Args:
            driver: Selenium WebDriver 인스턴스
            timeout: 대기 타임아웃 (초)
            manual_mode: 수동 로그인 모드 (사용자가 직접 브라우저에서 로그인)
        """
        self.driver = driver
        self.timeout = timeout
        self.manual_mode = manual_mode
        self._is_mac = platform.system() == "Darwin"

    def _get_paste_key(self) -> str:
        """OS에 따른 붙여넣기 키 반환"""
        return Keys.COMMAND if self._is_mac else Keys.CONTROL

    def _input_text_via_clipboard(self, element, text: str):
        """
        클립보드를 통한 텍스트 입력 (봇 탐지 우회)

        Args:
            element: 입력할 WebElement
            text: 입력할 텍스트
        """
        # 요소 클릭하여 포커스
        element.click()
        time.sleep(0.3)

        # 기존 내용 삭제
        paste_key = self._get_paste_key()
        element.send_keys(paste_key, 'a')
        time.sleep(0.1)
        element.send_keys(Keys.DELETE)
        time.sleep(0.1)

        # 방법 1: 클립보드 붙여넣기 시도
        try:
            pyperclip.copy(text)
            element.send_keys(paste_key, 'v')
            time.sleep(0.3)

            # 입력 확인
            if element.get_attribute('value') == text:
                pyperclip.copy('')  # 클립보드 비우기
                return
        except Exception:
            pass

        # 방법 2: 한 글자씩 입력 (더 자연스러운 방식)
        element.clear()
        time.sleep(0.2)
        for char in text:
            element.send_keys(char)
            time.sleep(0.05)  # 타이핑 딜레이

        pyperclip.copy('')  # 클립보드 비우기

    def login(self, user_id: str, password: str) -> bool:
        """
        네이버 로그인 수행

        Args:
            user_id: 네이버 아이디
            password: 네이버 비밀번호

        Returns:
            로그인 성공 여부

        Raises:
            CaptchaDetectedError: 캡차가 감지된 경우
            NaverLoginError: 기타 로그인 오류
        """
        try:
            logger.info("네이버 로그인 페이지로 이동")
            self.driver.get(NAVER_LOGIN_URL)
            time.sleep(2)  # 페이지 완전 로딩 대기

            # 수동 로그인 모드
            if self.manual_mode:
                return self._manual_login()

            # 아이디 입력 필드 대기
            id_input = WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.ID_INPUT_SELECTOR))
            )

            # 비밀번호 입력 필드
            pw_input = self.driver.find_element(By.CSS_SELECTOR, self.PW_INPUT_SELECTOR)

            # 아이디 입력
            logger.debug("아이디 입력 중...")
            self._input_text_via_clipboard(id_input, user_id)
            time.sleep(0.5)

            # 비밀번호 입력
            logger.debug("비밀번호 입력 중...")
            self._input_text_via_clipboard(pw_input, password)
            time.sleep(0.5)

            # 로그인 버튼 클릭
            logger.debug("로그인 버튼 클릭")
            login_button = self.driver.find_element(
                By.CSS_SELECTOR, self.LOGIN_BUTTON_SELECTOR
            )
            login_button.click()

            # 로그인 결과 확인 (3초 대기)
            time.sleep(3)

            # 캡차 확인 - 수동 처리 요청
            if self._check_captcha():
                logger.warning("캡차가 감지되었습니다. 브라우저에서 직접 처리해주세요.")
                return self._wait_for_manual_login()

            # 로그인 에러 확인
            error_msg = self._check_login_error()
            if error_msg:
                raise NaverLoginError(f"로그인 실패: {error_msg}")

            # 로그인 성공 확인
            if self.is_logged_in():
                logger.info("네이버 로그인 성공")
                return True
            else:
                # 아직 로그인 페이지면 수동 처리 요청
                logger.warning("로그인이 완료되지 않았습니다. 브라우저에서 직접 로그인해주세요.")
                return self._wait_for_manual_login()

        except CaptchaDetectedError:
            raise
        except NaverLoginError:
            raise
        except TimeoutException:
            raise NaverLoginError("로그인 페이지 로딩 타임아웃")
        except Exception as e:
            raise NaverLoginError(f"로그인 중 예기치 않은 오류: {e}")

    def _manual_login(self) -> bool:
        """수동 로그인 모드 - 사용자가 브라우저에서 직접 로그인"""
        print("\n" + "=" * 50)
        print("수동 로그인 모드")
        print("=" * 50)
        print("브라우저에서 직접 로그인해주세요.")
        print("로그인 완료 후 Enter 키를 누르세요...")
        print("=" * 50)

        try:
            input()
        except EOFError:
            # 비대화형 환경에서는 대기
            return self._wait_for_login_completion(timeout=120)

        return self.is_logged_in()

    def _wait_for_manual_login(self, timeout: int = 60) -> bool:
        """사용자가 수동으로 캡차/로그인을 처리할 때까지 대기"""
        print("\n" + "=" * 50)
        print("브라우저에서 캡차를 입력하거나 로그인을 완료해주세요.")
        print(f"최대 {timeout}초 동안 대기합니다...")
        print("=" * 50)

        return self._wait_for_login_completion(timeout)

    def _wait_for_login_completion(self, timeout: int = 60) -> bool:
        """로그인 완료까지 대기"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_logged_in():
                logger.info("로그인 성공 확인")
                return True
            time.sleep(2)

        logger.error(f"{timeout}초 내에 로그인이 완료되지 않았습니다.")
        return False

    def _check_captcha(self) -> bool:
        """캡차 존재 여부 확인"""
        try:
            self.driver.find_element(By.CSS_SELECTOR, self.CAPTCHA_SELECTOR)
            return True
        except NoSuchElementException:
            return False

    def _check_login_error(self) -> str:
        """로그인 에러 메시지 확인"""
        try:
            error_element = self.driver.find_element(
                By.CSS_SELECTOR, self.LOGIN_ERROR_SELECTOR
            )
            if error_element.is_displayed():
                return error_element.text
        except NoSuchElementException:
            pass
        return ""

    def is_logged_in(self) -> bool:
        """
        로그인 상태 확인

        Returns:
            로그인 되어있으면 True
        """
        try:
            # 로그인 후 URL 변경 확인
            current_url = self.driver.current_url

            # 로그인 페이지가 아니면 성공으로 간주
            if "nidlogin" not in current_url and "login" not in current_url.lower():
                return True

            # 네이버 메인이나 다른 페이지로 리다이렉트되었는지 확인
            if "naver.com" in current_url and "nid.naver.com" not in current_url:
                return True

            return False

        except Exception as e:
            logger.warning(f"로그인 상태 확인 중 오류: {e}")
            return False

    def navigate_to_cafe(self, cafe_id: str) -> bool:
        """
        로그인 후 특정 카페로 이동

        Args:
            cafe_id: 카페 ID (URL의 카페명)

        Returns:
            이동 성공 여부
        """
        try:
            cafe_url = f"https://cafe.naver.com/{cafe_id}"
            logger.info(f"카페로 이동: {cafe_url}")
            self.driver.get(cafe_url)
            time.sleep(2)

            # 카페 페이지 로딩 확인
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.ID, "cafe_main"))
            )

            logger.info("카페 페이지 로딩 완료")
            return True

        except TimeoutException:
            logger.error("카페 페이지 로딩 타임아웃")
            return False
        except Exception as e:
            logger.error(f"카페 이동 중 오류: {e}")
            return False
