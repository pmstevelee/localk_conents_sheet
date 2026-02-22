#!/bin/bash
# 네이버 카페 크롤러 설치 스크립트 (macOS / Linux)

set -e

echo "============================================"
echo "  네이버 카페 크롤러 설치"
echo "============================================"

# Python 버전 확인
if ! command -v python3 &>/dev/null; then
    echo "[오류] Python3가 설치되어 있지 않습니다."
    echo "  macOS: brew install python3"
    echo "  Ubuntu: sudo apt install python3 python3-pip"
    exit 1
fi

PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python $PYTHON_VER 감지됨"

# pip 확인
if ! command -v pip3 &>/dev/null && ! python3 -m pip --version &>/dev/null; then
    echo "[오류] pip가 설치되어 있지 않습니다."
    echo "  python3 -m ensurepip --upgrade"
    exit 1
fi

# 가상 환경 생성
echo ""
echo "[1/3] 가상 환경 생성 중..."
python3 -m venv .venv
source .venv/bin/activate

# 패키지 설치
echo "[2/3] 패키지 설치 중..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "      설치 완료!"

# 실행 스크립트 생성
echo "[3/3] 실행 스크립트 생성 중..."
cat > run.sh <<'RUNEOF'
#!/bin/bash
source "$(dirname "$0")/.venv/bin/activate"
python3 "$(dirname "$0")/main.py"
RUNEOF
chmod +x run.sh

echo ""
echo "============================================"
echo "  설치 완료!"
echo ""
echo "  실행 방법:"
echo "    ./run.sh"
echo ""
echo "  또는:"
echo "    source .venv/bin/activate"
echo "    python main.py"
echo "============================================"
