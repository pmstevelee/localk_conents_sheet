#!/usr/bin/env python3
"""
네이버 카페 크롤러 웹 인터페이스
Flask 기반 로컬 웹 앱
"""
import os
import sys
import json
import logging
import threading
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from src.crawler.cafe_crawler import CafeCrawler, CrawlerError
from src.crawler.board_parser import Board
from config.settings import OUTPUT_DIR, LOG_DIR

app = Flask(__name__)
app.secret_key = 'naver-cafe-crawler-secret-key'

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 크롤링 상태 저장
crawl_status = {
    'is_running': False,
    'progress': '',
    'result': None,
    'error': None,
    'logs': []
}

# 크롤러 인스턴스 (수동 로그인용)
active_crawler = None


def add_log(message: str):
    """로그 메시지 추가"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    crawl_status['logs'].append(f"[{timestamp}] {message}")
    # 최대 100개 로그 유지
    if len(crawl_status['logs']) > 100:
        crawl_status['logs'] = crawl_status['logs'][-100:]


@app.route('/')
def index():
    """메인 페이지"""
    # 기존 CSV 파일 목록
    csv_files = []
    if OUTPUT_DIR.exists():
        for f in sorted(OUTPUT_DIR.glob('*.csv'), key=os.path.getmtime, reverse=True):
            csv_files.append({
                'name': f.name,
                'size': f"{f.stat().st_size / 1024:.1f} KB",
                'date': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            })

    return render_template('index.html', csv_files=csv_files[:10])


@app.route('/start', methods=['POST'])
def start_crawl():
    """크롤링 시작"""
    global active_crawler, crawl_status

    if crawl_status['is_running']:
        return jsonify({'success': False, 'error': '이미 크롤링이 진행 중입니다.'})

    # 폼 데이터 가져오기
    cafe_id = request.form.get('cafe_id', '').strip()
    user_id = request.form.get('user_id', '').strip()
    password = request.form.get('password', '').strip()
    board_input = request.form.get('board_input', '').strip()
    board_url = request.form.get('board_url', '').strip()
    crawl_all = request.form.get('crawl_all') == 'on'
    max_posts = int(request.form.get('max_posts', 20))
    max_pages = int(request.form.get('max_pages', 1))

    # 유효성 검사
    if not cafe_id:
        return jsonify({'success': False, 'error': '카페 ID를 입력하세요.'})
    if not user_id:
        return jsonify({'success': False, 'error': '네이버 아이디를 입력하세요.'})

    # 상태 초기화
    crawl_status = {
        'is_running': True,
        'progress': '크롤러 시작 중...',
        'result': None,
        'error': None,
        'logs': []
    }

    # 백그라운드 스레드에서 크롤링 실행
    thread = threading.Thread(
        target=run_crawl,
        args=(cafe_id, user_id, password, board_input, board_url, crawl_all, max_posts, max_pages)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'success': True, 'message': '크롤링을 시작합니다.'})


def run_crawl(cafe_id, user_id, password, board_input, board_url, crawl_all, max_posts, max_pages):
    """백그라운드에서 크롤링 실행"""
    global active_crawler, crawl_status

    crawler = None
    try:
        add_log(f"카페 '{cafe_id}' 크롤링 시작")
        crawl_status['progress'] = '브라우저 시작 중...'

        # 크롤러 생성
        crawler = CafeCrawler(
            cafe_id=cafe_id,
            user_id=user_id,
            password=password,
            headless=False,
            manual_login=True  # 웹에서는 항상 수동 로그인
        )
        active_crawler = crawler

        # 브라우저 시작
        crawler.start()
        add_log("브라우저 시작 완료")

        # 로그인
        crawl_status['progress'] = '로그인 대기 중... (브라우저에서 로그인하세요)'
        add_log("브라우저에서 로그인해주세요")

        if not crawler.login():
            raise CrawlerError("로그인 실패")

        add_log("로그인 성공")

        # 게시판 결정
        board = None

        if board_url:
            # URL로 게시판 파싱
            crawl_status['progress'] = '게시판 URL 파싱 중...'
            board = crawler.parse_board_url(board_url)
            if not board:
                raise CrawlerError(f"게시판 URL 파싱 실패: {board_url}")
            add_log(f"게시판 URL 파싱 완료: ID={board.board_id}")
        else:
            # 게시판 목록 조회
            crawl_status['progress'] = '게시판 목록 조회 중...'
            boards = crawler.get_boards()
            add_log(f"{len(boards)}개 게시판 발견")

            if board_input:
                # ID 또는 이름으로 게시판 찾기
                board = crawler.find_board(boards, board_input)
                if not board:
                    raise CrawlerError(f"'{board_input}' 게시판을 찾을 수 없습니다.")
                add_log(f"게시판 선택: {board.name}")
            else:
                # 게시판 미지정 시 첫 번째 게시판 사용
                if boards:
                    board = boards[0]
                    add_log(f"첫 번째 게시판 선택: {board.name}")
                else:
                    raise CrawlerError("게시판을 찾을 수 없습니다.")

        # 게시글 크롤링
        crawl_status['progress'] = f"'{board.name}' 게시글 수집 중..."
        add_log(f"게시글 크롤링 시작 (최대 {max_posts}개, {max_pages}페이지)")

        posts = crawler.crawl_posts(
            board,
            max_posts=max_posts,
            max_pages=max_pages,
            today_only=not crawl_all
        )

        if not posts:
            add_log("수집된 게시글 없음")
            crawl_status['progress'] = '완료 (수집된 게시글 없음)'
            crawl_status['result'] = {
                'success': True,
                'posts': 0,
                'comments': 0,
                'file': None
            }
        else:
            # CSV 저장
            crawl_status['progress'] = 'CSV 저장 중...'
            filepath = crawler.save_to_csv(posts, board.name)

            total_comments = sum(len(p.comments) for p in posts)
            add_log(f"크롤링 완료: {len(posts)}개 게시글, {total_comments}개 댓글")
            add_log(f"파일 저장: {filepath}")

            crawl_status['progress'] = '완료!'
            crawl_status['result'] = {
                'success': True,
                'posts': len(posts),
                'comments': total_comments,
                'file': os.path.basename(filepath)
            }

    except Exception as e:
        logger.exception(f"크롤링 오류: {e}")
        add_log(f"오류 발생: {e}")
        crawl_status['error'] = str(e)
        crawl_status['progress'] = f'오류: {e}'

    finally:
        crawl_status['is_running'] = False
        if crawler:
            try:
                crawler.close()
            except:
                pass
        active_crawler = None


@app.route('/status')
def get_status():
    """크롤링 상태 조회"""
    return jsonify({
        'is_running': crawl_status['is_running'],
        'progress': crawl_status['progress'],
        'result': crawl_status['result'],
        'error': crawl_status['error'],
        'logs': crawl_status['logs'][-20:]  # 최근 20개 로그
    })


@app.route('/stop', methods=['POST'])
def stop_crawl():
    """크롤링 중지"""
    global active_crawler, crawl_status

    if active_crawler:
        try:
            active_crawler.close()
        except:
            pass
        active_crawler = None

    crawl_status['is_running'] = False
    crawl_status['progress'] = '사용자에 의해 중지됨'
    add_log("크롤링 중지")

    return jsonify({'success': True})


@app.route('/download/<filename>')
def download_file(filename):
    """CSV 파일 다운로드"""
    filepath = OUTPUT_DIR / filename
    if filepath.exists():
        return send_file(filepath, as_attachment=True)
    return "파일을 찾을 수 없습니다.", 404


@app.route('/files')
def list_files():
    """CSV 파일 목록"""
    csv_files = []
    if OUTPUT_DIR.exists():
        for f in sorted(OUTPUT_DIR.glob('*.csv'), key=os.path.getmtime, reverse=True):
            csv_files.append({
                'name': f.name,
                'size': f"{f.stat().st_size / 1024:.1f} KB",
                'date': datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            })
    return jsonify(csv_files)


@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    """CSV 파일 삭제"""
    filepath = OUTPUT_DIR / filename
    if filepath.exists():
        try:
            filepath.unlink()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다.'})


if __name__ == '__main__':
    port = 5001
    print("\n" + "=" * 50)
    print("네이버 카페 크롤러 웹 서버")
    print("=" * 50)
    print(f"브라우저에서 http://localhost:{port} 접속")
    print("종료: Ctrl+C")
    print("=" * 50 + "\n")

    app.run(host='0.0.0.0', port=port, debug=False)
