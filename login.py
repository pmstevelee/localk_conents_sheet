"""
네이버 로그인 모듈
- RSA 공개키 기반 비밀번호 암호화 후 로그인
- 세션 쿠키 유지 및 재사용
"""

import time
import binascii
import requests
from bs4 import BeautifulSoup
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5

import config


class NaverLoginError(Exception):
    """로그인 실패 예외"""
    pass


class NaverLogin:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.DEFAULT_HEADERS)
        self._logged_in = False

    def _get_rsa_key(self) -> dict:
        """
        네이버 RSA 공개키 조회
        반환: {"keyName": str, "e": str, "n": str}
        """
        resp = self.session.get(
            config.NAVER_RSA_KEY_URL,
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        key_data = resp.json()
        return key_data

    def _encrypt_password(self, key_name: str, e_hex: str, n_hex: str,
                           naver_id: str, password: str) -> str:
        """
        RSA PKCS1_v1_5로 ID+PW 암호화
        메시지 형식: \0{len(key_name)}{key_name}{len(id)}{id}{len(pw)}{pw}
        반환: 16진수 문자열
        """
        # 메시지 조립
        key_name_bytes = key_name.encode("utf-8")
        id_bytes = naver_id.encode("utf-8")
        pw_bytes = password.encode("utf-8")

        message = (
            b"\x00"
            + bytes([len(key_name_bytes)]) + key_name_bytes
            + bytes([len(id_bytes)]) + id_bytes
            + bytes([len(pw_bytes)]) + pw_bytes
        )

        # RSA 공개키 객체 생성 (n, e는 16진수 → int)
        n = int(n_hex, 16)
        e = int(e_hex, 16)
        pub_key = RSA.construct((n, e))
        cipher = PKCS1_v1_5.new(pub_key)

        encrypted = cipher.encrypt(message)
        return binascii.hexlify(encrypted).decode("ascii")

    def _get_login_form_data(self) -> dict:
        """로그인 페이지에서 hidden input 값 추출"""
        resp = self.session.get(
            config.NAVER_LOGIN_URL,
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        form_data = {}
        for inp in soup.select("input[type='hidden']"):
            name = inp.get("name")
            value = inp.get("value", "")
            if name:
                form_data[name] = value
        return form_data

    def login(self, naver_id: str, password: str) -> bool:
        """
        네이버 로그인 수행
        Args:
            naver_id: 네이버 아이디
            password: 비밀번호
        Returns:
            로그인 성공 여부
        Raises:
            NaverLoginError: 로그인 실패 시
        """
        # 1. RSA 공개키 획득
        key_data = self._get_rsa_key()
        key_name = key_data["keyName"]
        e_hex = key_data["e"]
        n_hex = key_data["n"]

        # 2. 비밀번호 RSA 암호화
        enc_pw = self._encrypt_password(key_name, e_hex, n_hex, naver_id, password)

        # 3. 로그인 폼 데이터 가져오기
        time.sleep(0.5)
        form_data = self._get_login_form_data()

        # 4. 로그인 POST 요청
        login_payload = {
            **form_data,
            "svctype": "0",
            "enctp": "1",
            "encnm": key_name,
            "enc_url": "http0X0.0000000000001P-10220.0000000000001P-10221P-10221P-10222P-10222",
            "url": "https://www.naver.com",
            "smart_LEVEL": "-1",
            "encpw": enc_pw,
        }

        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": config.NAVER_LOGIN_URL,
        })

        resp = self.session.post(
            config.NAVER_LOGIN_URL,
            data=login_payload,
            timeout=config.REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        # 5. 로그인 성공 여부 확인
        if self._check_login_success():
            self._logged_in = True
            return True

        # 실패 원인 분석
        if "captcha" in resp.text.lower():
            raise NaverLoginError(
                "캡차(CAPTCHA)가 감지되었습니다. 브라우저에서 직접 로그인 후 쿠키를 사용하세요."
            )
        if "otp" in resp.text.lower() or "2단계" in resp.text:
            raise NaverLoginError(
                "2단계 인증이 필요합니다. 네이버 앱에서 2단계 인증을 비활성화하세요."
            )

        raise NaverLoginError("로그인에 실패했습니다. 아이디/비밀번호를 확인하세요.")

    def _check_login_success(self) -> bool:
        """로그인 성공 여부 확인 (네이버 메인 접속 후 쿠키 확인)"""
        resp = self.session.get(
            "https://www.naver.com",
            timeout=config.REQUEST_TIMEOUT,
        )
        # NID_AUT 쿠키가 있으면 로그인 성공
        return "NID_AUT" in self.session.cookies

    def load_cookies_from_string(self, cookie_str: str) -> None:
        """
        브라우저에서 복사한 쿠키 문자열로 세션 설정
        (캡차/2FA 우회용 수동 로그인 대안)
        형식: "key1=value1; key2=value2; ..."
        """
        for item in cookie_str.split(";"):
            if "=" in item:
                key, _, value = item.strip().partition("=")
                self.session.cookies.set(key.strip(), value.strip())
        self._logged_in = True

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    def get_session(self) -> requests.Session:
        """인증된 세션 반환"""
        if not self._logged_in:
            raise NaverLoginError("로그인이 필요합니다.")
        return self.session

    def logout(self) -> None:
        """로그아웃"""
        try:
            self.session.get(config.NAVER_LOGOUT_URL, timeout=10)
        except Exception:
            pass
        self.session.cookies.clear()
        self._logged_in = False
