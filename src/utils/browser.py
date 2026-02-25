"""
Selenium WebDriver 설정 및 관리
봇 탐지 우회 설정 포함
"""
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

import sys
sys.path.append(str(__file__).rsplit('/', 3)[0])
from config.settings import USER_AGENT

logger = logging.getLogger(__name__)


class BrowserManager:
    """Chrome WebDriver 관리 클래스"""

    def __init__(self, headless: bool = False):
        """
        Args:
            headless: 헤드리스 모드 사용 여부 (봇 탐지 우회를 위해 False 권장)
        """
        self.headless = headless
        self.driver = None

    def create_driver(self) -> webdriver.Chrome:
        """
        봇 탐지 우회 설정이 적용된 Chrome WebDriver 생성

        Returns:
            설정된 Chrome WebDriver 인스턴스
        """
        options = Options()

        # 봇 탐지 우회 설정
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # User-Agent 설정
        options.add_argument(f"user-agent={USER_AGENT}")

        # 기본 설정
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")

        # 언어 설정
        options.add_argument("--lang=ko_KR")

        # 헤드리스 모드 (탐지 위험 있음)
        if self.headless:
            options.add_argument("--headless=new")
            logger.warning("헤드리스 모드는 봇 탐지 위험이 있습니다.")

        # 드라이버 생성
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            logger.error(f"ChromeDriver 설치/실행 실패: {e}")
            raise

        # navigator.webdriver 속성 제거 (봇 탐지 우회)
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ko-KR', 'ko', 'en-US', 'en']
                    });
                """
            }
        )

        # 타임아웃 설정
        self.driver.implicitly_wait(5)
        self.driver.set_page_load_timeout(30)

        logger.info("Chrome WebDriver 초기화 완료")
        return self.driver

    def close(self):
        """WebDriver 종료"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver 종료 완료")
            except Exception as e:
                logger.warning(f"WebDriver 종료 중 오류: {e}")
            finally:
                self.driver = None
