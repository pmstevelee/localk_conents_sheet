#!/usr/bin/env python3
"""
네이버 로그인 테스트 스크립트
입력 방식 디버깅용
"""
import time
import sys
import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def test_login(user_id: str, password: str):
    """로그인 테스트"""

    print("=" * 50)
    print("네이버 로그인 테스트")
    print("=" * 50)

    # Chrome 옵션 설정
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ko_KR")

    print("브라우저 시작 중...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # navigator.webdriver 숨기기
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"}
    )

    try:
        # 로그인 페이지로 이동
        print("로그인 페이지 이동...")
        driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(3)

        # 현재 페이지 정보 출력
        print(f"현재 URL: {driver.current_url}")
        print(f"페이지 제목: {driver.title}")

        # 입력 필드 찾기
        print("\n입력 필드 확인 중...")

        # 여러 셀렉터 시도
        id_selectors = ["#id", "input[name='id']", "input#id", ".input_id"]
        pw_selectors = ["#pw", "input[name='pw']", "input#pw", ".input_pw"]

        id_input = None
        pw_input = None

        for sel in id_selectors:
            try:
                id_input = driver.find_element(By.CSS_SELECTOR, sel)
                print(f"✓ ID 필드 발견: {sel}")
                break
            except:
                print(f"✗ ID 필드 없음: {sel}")

        for sel in pw_selectors:
            try:
                pw_input = driver.find_element(By.CSS_SELECTOR, sel)
                print(f"✓ PW 필드 발견: {sel}")
                break
            except:
                print(f"✗ PW 필드 없음: {sel}")

        if not id_input or not pw_input:
            print("\n입력 필드를 찾을 수 없습니다!")
            # 페이지 소스 일부 출력
            print("\n페이지 내 input 요소들:")
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for inp in inputs[:10]:
                print(f"  - id={inp.get_attribute('id')}, name={inp.get_attribute('name')}, type={inp.get_attribute('type')}")
            return

        print("\n=== 입력 방식 테스트 ===")

        # 방법 1: JavaScript로 직접 값 설정
        print("\n[방법 1] JavaScript 값 설정...")
        driver.execute_script(f"arguments[0].value = '{user_id}';", id_input)
        time.sleep(0.5)
        print(f"  ID 필드 값: {id_input.get_attribute('value')}")

        # 값이 비어있으면 다른 방법 시도
        if not id_input.get_attribute('value'):
            print("  -> 실패, 다른 방법 시도...")

            # 방법 2: 클릭 후 send_keys
            print("\n[방법 2] click + send_keys...")
            id_input.click()
            time.sleep(0.3)
            id_input.clear()
            id_input.send_keys(user_id)
            time.sleep(0.5)
            print(f"  ID 필드 값: {id_input.get_attribute('value')}")

        if not id_input.get_attribute('value'):
            # 방법 3: ActionChains
            print("\n[방법 3] ActionChains...")
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver)
            actions.move_to_element(id_input)
            actions.click()
            actions.send_keys(user_id)
            actions.perform()
            time.sleep(0.5)
            print(f"  ID 필드 값: {id_input.get_attribute('value')}")

        if not id_input.get_attribute('value'):
            # 방법 4: 클립보드 붙여넣기 (Mac)
            print("\n[방법 4] 클립보드 붙여넣기...")
            pyperclip.copy(user_id)
            id_input.click()
            time.sleep(0.2)
            id_input.send_keys(Keys.COMMAND, 'v')
            time.sleep(0.5)
            print(f"  ID 필드 값: {id_input.get_attribute('value')}")

        # 비밀번호 입력
        print("\n비밀번호 입력 중...")
        pw_input.click()
        time.sleep(0.3)

        # JavaScript로 시도
        driver.execute_script(f"arguments[0].value = '{password}';", pw_input)
        time.sleep(0.5)

        if not pw_input.get_attribute('value'):
            pw_input.send_keys(password)
            time.sleep(0.5)

        print(f"  PW 필드 값 길이: {len(pw_input.get_attribute('value') or '')}")

        # 로그인 버튼 찾기
        print("\n로그인 버튼 찾는 중...")
        btn_selectors = [
            "#log\\.login",
            ".btn_login",
            "button[type='submit']",
            ".btn_global",
            "#login_submit"
        ]

        login_btn = None
        for sel in btn_selectors:
            try:
                login_btn = driver.find_element(By.CSS_SELECTOR, sel)
                print(f"✓ 로그인 버튼 발견: {sel}")
                break
            except:
                print(f"✗ 버튼 없음: {sel}")

        if login_btn:
            print("\n로그인 버튼 클릭...")
            login_btn.click()
            time.sleep(5)

            print(f"\n로그인 후 URL: {driver.current_url}")

            if "nidlogin" not in driver.current_url:
                print("✓ 로그인 성공으로 보임!")
            else:
                print("✗ 아직 로그인 페이지에 있음")
                # 에러 메시지 확인
                try:
                    err = driver.find_element(By.CSS_SELECTOR, "#err_common, .error_message")
                    print(f"  에러: {err.text}")
                except:
                    pass

        print("\n30초 후 브라우저가 닫힙니다...")
        time.sleep(30)

    finally:
        driver.quit()
        print("테스트 종료")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("사용법: python test_login.py <아이디> <비밀번호>")
        sys.exit(1)

    test_login(sys.argv[1], sys.argv[2])
