@echo off
chcp 65001 > nul
echo ============================================
echo   네이버 카페 크롤러 설치 (Windows)
echo ============================================

:: Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo   https://www.python.org/downloads/ 에서 설치하세요.
    echo   설치 시 "Add Python to PATH" 체크 필수!
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Python %PYVER% 감지됨

:: 가상 환경 생성
echo.
echo [1/3] 가상 환경 생성 중...
python -m venv .venv
if errorlevel 1 (
    echo [오류] 가상 환경 생성 실패
    pause
    exit /b 1
)

:: 패키지 설치
echo [2/3] 패키지 설치 중...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
echo       설치 완료!

:: 실행 배치 파일 생성
echo [3/3] 실행 파일 생성 중...
(
echo @echo off
echo chcp 65001 ^> nul
echo call "%~dp0.venv\Scripts\activate.bat"
echo python "%~dp0main.py"
echo pause
) > run.bat

echo.
echo ============================================
echo   설치 완료!
echo.
echo   실행 방법:
echo     run.bat  (더블클릭 또는 명령 프롬프트에서 실행)
echo.
echo   또는 명령 프롬프트에서:
echo     .venv\Scripts\activate
echo     python main.py
echo ============================================
pause
