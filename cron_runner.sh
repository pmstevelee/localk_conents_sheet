#!/bin/bash
#
# 네이버 카페 크롤러 자동 실행 스크립트
# cron에서 매일 실행하도록 설정
#
# 사용법:
#   crontab -e 로 열고 아래 내용 추가:
#   # 매일 오후 11시 55분에 실행
#   55 23 * * * /path/to/cron_runner.sh
#

# 프로젝트 경로 설정
PROJECT_DIR="/Users/jj_imac/Downloads/localk_contents_cafe"
VENV_PATH="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/cron_$(date +%Y%m%d_%H%M%S).log"

# 로그 디렉토리 생성
mkdir -p "$LOG_DIR"

echo "========================================" >> "$LOG_FILE"
echo "크롤러 시작: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# .env 파일 로드
if [ -f "$PROJECT_DIR/.env" ]; then
    source "$PROJECT_DIR/.env"
else
    echo "오류: .env 파일이 없습니다." >> "$LOG_FILE"
    exit 1
fi

# 필수 환경 변수 확인
if [ -z "$NAVER_USER_ID" ] || [ -z "$NAVER_PASSWORD" ] || [ -z "$NAVER_CAFE_ID" ] || [ -z "$TARGET_BOARD_ID" ]; then
    echo "오류: 필수 환경 변수가 설정되지 않았습니다." >> "$LOG_FILE"
    echo "NAVER_USER_ID, NAVER_PASSWORD, NAVER_CAFE_ID, TARGET_BOARD_ID 확인 필요" >> "$LOG_FILE"
    exit 1
fi

# 가상환경 활성화 (있는 경우)
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
fi

# Python 경로 설정 (필요한 경우)
export PATH="/usr/local/bin:/usr/bin:$PATH"

# 크롤러 실행
cd "$PROJECT_DIR"

# 헤드리스 옵션
HEADLESS_OPT=""
if [ "$HEADLESS" = "true" ]; then
    HEADLESS_OPT="--headless"
fi

# 컴팩트 옵션
COMPACT_OPT=""
if [ "$COMPACT_CSV" = "true" ]; then
    COMPACT_OPT="--compact"
fi

python3 main.py \
    --cafe "$NAVER_CAFE_ID" \
    --user "$NAVER_USER_ID" \
    --password "$NAVER_PASSWORD" \
    --board "$TARGET_BOARD_ID" \
    $HEADLESS_OPT \
    $COMPACT_OPT \
    >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

echo "========================================" >> "$LOG_FILE"
echo "크롤러 종료: $(date)" >> "$LOG_FILE"
echo "종료 코드: $EXIT_CODE" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 가상환경 비활성화
if [ -d "$VENV_PATH" ]; then
    deactivate 2>/dev/null
fi

exit $EXIT_CODE
