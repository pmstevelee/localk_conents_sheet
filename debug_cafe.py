#!/usr/bin/env python3
"""카페 구조 디버깅 스크립트"""
import time
import sys
sys.path.insert(0, '.')

from src.utils.browser import BrowserManager
from src.utils.iframe_handler import IframeHandler

def debug_cafe(cafe_id: str):
    print("브라우저 시작...")
    browser = BrowserManager(headless=False)
    driver = browser.create_driver()
    iframe_handler = IframeHandler(driver)

    try:
        # 카페 URL에서 로그인 시작 (로그인 후 카페로 돌아옴)
        cafe_url = f"https://cafe.naver.com/{cafe_id}"
        print(f"\n먼저 카페로 이동: {cafe_url}")
        driver.get(cafe_url)
        time.sleep(3)

        print("\n" + "=" * 50)
        print("브라우저에서 로그인해주세요.")
        print("90초 동안 대기합니다...")
        print("=" * 50)

        # 로그인 완료 대기 (최대 90초)
        for i in range(90):
            time.sleep(1)
            current = driver.current_url
            # 카페 페이지에 있으면 완료
            if "cafe.naver.com" in current and "nidlogin" not in current:
                print("카페 페이지 감지됨!")
                break
            if i % 10 == 0:
                print(f"  대기 중... {90-i}초 남음 (URL: {current[:50]})")

        # URL 확인
        print(f"\n현재 URL: {driver.current_url}")

        print(f"\n현재 URL: {driver.current_url}")

        # iframe 전환
        print("\niframe 전환 시도...")
        if iframe_handler.switch_to_cafe_main():
            print("iframe 전환 성공!")
        else:
            print("iframe 전환 실패")

        # 메뉴 요소 찾기
        print("\n=== 메뉴 요소 탐색 ===")

        selectors_to_try = [
            "ul.cafe-menu-list",
            ".cafe-menu-list",
            "#menuLink",
            ".menu-list",
            "ul.cafe-menu",
            ".gnb_menu",
            "#cafe-menu",
            ".cafe_menu",
            "nav",
            ".sidebar",
            "#cafe_main_menu",
            "ul[class*='menu']",
            "div[class*='menu']",
        ]

        from selenium.webdriver.common.by import By

        for sel in selectors_to_try:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    print(f"✓ {sel}: {len(elems)}개 발견")
                    for i, elem in enumerate(elems[:2]):
                        text = elem.text[:100].replace('\n', ' ')
                        print(f"    [{i}] {text}...")
            except Exception as e:
                print(f"✗ {sel}: {e}")

        # 모든 링크 찾기
        print("\n=== 링크 탐색 ===")
        links = driver.find_elements(By.TAG_NAME, "a")
        print(f"총 {len(links)}개의 링크 발견")

        # menuid가 포함된 링크 찾기
        menu_links = []
        for link in links:
            href = link.get_attribute("href") or ""
            if "menuid" in href.lower() or "menu" in href.lower():
                text = link.text.strip()[:30]
                if text:
                    menu_links.append((text, href))

        print(f"\nmenu 관련 링크: {len(menu_links)}개")
        for text, href in menu_links[:20]:
            print(f"  - {text}: {href[:80]}")

        # 페이지 소스 일부 저장
        print("\n페이지 소스를 cafe_debug.html로 저장 중...")
        with open("cafe_debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("저장 완료!")

        print("\n30초 후 브라우저가 닫힙니다...")
        time.sleep(30)

    finally:
        driver.quit()


if __name__ == "__main__":
    cafe_id = sys.argv[1] if len(sys.argv) > 1 else "iliveincan"
    debug_cafe(cafe_id)
