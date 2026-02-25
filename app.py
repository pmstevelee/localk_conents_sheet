"""
네이버 카페 크롤러 웹 애플리케이션
크롤링, QA 추출, 수집 제외 키워드 관리 통합
"""
import os
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash

# 프로젝트 경로 설정
import sys
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import OUTPUT_DIR, CONFIG_DIR, exclude_keywords_manager
from src.storage.qa_extractor import QAExtractor
from src.crawler.cafe_crawler import CafeCrawler
from src.crawler.board_parser import Board

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 설정 파일
CRAWLER_CONFIG_FILE = CONFIG_DIR / 'crawler_config.json'

# 크롤링 상태 관리
crawl_status = {
    'is_running': False,
    'progress': '',
    'last_result': None,
    'error': None
}


def load_crawler_config():
    """크롤러 설정 로드"""
    default_config = {
        'cafe_id': '',
        'user_id': '',
        'password': '',
        'board_url': '',
        'max_posts': 50,
        'max_pages': 5,
        'today_only': True,
        'headless': False
    }

    if CRAWLER_CONFIG_FILE.exists():
        try:
            with open(CRAWLER_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 기본값과 병합
                return {**default_config, **config}
        except Exception:
            pass

    return default_config


def save_crawler_config(config):
    """크롤러 설정 저장 (비밀번호 제외)"""
    save_config = {k: v for k, v in config.items() if k != 'password'}
    try:
        with open(CRAWLER_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"설정 저장 실패: {e}")


def get_file_list():
    """파일 목록 조회"""
    csv_files = []
    qa_files = []

    for f in OUTPUT_DIR.glob('*.csv'):
        stat = f.stat()
        file_info = {
            'name': f.name,
            'size': f"{stat.st_size / 1024:.1f} KB",
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
        }

        if 'qa_extracted' in f.name:
            qa_files.append(file_info)
        else:
            csv_files.append(file_info)

    csv_files.sort(key=lambda x: x['modified'], reverse=True)
    qa_files.sort(key=lambda x: x['modified'], reverse=True)

    return csv_files, qa_files


# ===== 메인 페이지 =====

@app.route('/')
def index():
    """메인 페이지 - 크롤링"""
    config = load_crawler_config()
    csv_files, qa_files = get_file_list()
    exclude_keywords = exclude_keywords_manager.get_keywords()

    return render_template(
        'index.html',
        page='crawl',
        config=config,
        csv_files=csv_files,
        qa_files=qa_files,
        exclude_keywords=exclude_keywords,
        crawl_status=crawl_status
    )


@app.route('/qa')
def qa_page():
    """QA 추출 페이지"""
    csv_files, qa_files = get_file_list()
    exclude_keywords = exclude_keywords_manager.get_keywords()

    return render_template(
        'index.html',
        page='qa',
        csv_files=csv_files,
        qa_files=qa_files,
        exclude_keywords=exclude_keywords
    )


@app.route('/settings')
def settings_page():
    """설정 페이지"""
    config = load_crawler_config()
    exclude_keywords = exclude_keywords_manager.get_keywords()

    return render_template(
        'index.html',
        page='settings',
        config=config,
        exclude_keywords=exclude_keywords
    )


# ===== 크롤링 기능 =====

@app.route('/crawl/save-config', methods=['POST'])
def save_config():
    """크롤링 설정 저장"""
    config = {
        'cafe_id': request.form.get('cafe_id', '').strip(),
        'user_id': request.form.get('user_id', '').strip(),
        'board_url': request.form.get('board_url', '').strip(),
        'max_posts': int(request.form.get('max_posts', 50)),
        'max_pages': int(request.form.get('max_pages', 5)),
        'today_only': request.form.get('today_only') == 'on',
        'headless': request.form.get('headless') == 'on'
    }

    save_crawler_config(config)
    flash('설정이 저장되었습니다.', 'success')
    return redirect(url_for('index'))


def run_crawler_task(config, password):
    """백그라운드 크롤링 실행"""
    global crawl_status

    try:
        crawl_status['is_running'] = True
        crawl_status['progress'] = '크롤러 초기화 중...'
        crawl_status['error'] = None

        # 크롤러 생성
        crawler = CafeCrawler(
            cafe_id=config['cafe_id'],
            user_id=config['user_id'],
            password=password,
            headless=config.get('headless', False),
            manual_login=True,  # 수동 로그인 모드
            exclude_keywords=exclude_keywords_manager.get_keywords()
        )

        crawl_status['progress'] = '브라우저 시작 중...'
        crawler.start()

        crawl_status['progress'] = '로그인 대기 중... (브라우저에서 로그인해주세요)'
        if not crawler.login():
            raise Exception("로그인 실패")

        crawl_status['progress'] = '게시판 정보 파싱 중...'

        # 게시판 URL에서 Board 객체 생성
        board = crawler.parse_board_url(config['board_url'])
        if not board:
            raise Exception("게시판 URL을 파싱할 수 없습니다.")

        crawl_status['progress'] = f'게시글 크롤링 중... (최대 {config["max_posts"]}개)'

        # 크롤링 실행
        posts = crawler.crawl_posts(
            board,
            max_posts=config['max_posts'],
            max_pages=config['max_pages'],
            today_only=config.get('today_only', True)
        )

        if posts:
            crawl_status['progress'] = 'CSV 저장 중...'
            filepath = crawler.save_to_csv(posts, board.name)

            total_comments = sum(len(p.comments) for p in posts)
            crawl_status['last_result'] = {
                'success': True,
                'posts': len(posts),
                'comments': total_comments,
                'file': Path(filepath).name if filepath else None,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            crawl_status['progress'] = f'완료: {len(posts)}개 게시글, {total_comments}개 댓글'
        else:
            crawl_status['last_result'] = {
                'success': True,
                'posts': 0,
                'comments': 0,
                'file': None,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            crawl_status['progress'] = '크롤링할 게시글이 없습니다.'

        crawler.close()

    except Exception as e:
        logger.error(f"크롤링 오류: {e}")
        crawl_status['error'] = str(e)
        crawl_status['progress'] = f'오류: {str(e)}'
        crawl_status['last_result'] = {
            'success': False,
            'error': str(e),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    finally:
        crawl_status['is_running'] = False


@app.route('/crawl/start', methods=['POST'])
def start_crawl():
    """크롤링 시작"""
    global crawl_status

    if crawl_status['is_running']:
        flash('이미 크롤링이 진행 중입니다.', 'warning')
        return redirect(url_for('index'))

    # 설정 가져오기
    config = load_crawler_config()
    config['cafe_id'] = request.form.get('cafe_id', config.get('cafe_id', '')).strip()
    config['user_id'] = request.form.get('user_id', config.get('user_id', '')).strip()
    config['board_url'] = request.form.get('board_url', config.get('board_url', '')).strip()
    config['max_posts'] = int(request.form.get('max_posts', config.get('max_posts', 50)))
    config['max_pages'] = int(request.form.get('max_pages', config.get('max_pages', 5)))
    config['today_only'] = request.form.get('today_only') == 'on'
    config['headless'] = request.form.get('headless') == 'on'

    password = request.form.get('password', '').strip()

    # 필수 필드 검증
    if not config['cafe_id']:
        flash('카페 ID를 입력해주세요.', 'error')
        return redirect(url_for('index'))

    if not config['board_url']:
        flash('게시판 URL을 입력해주세요.', 'error')
        return redirect(url_for('index'))

    # 설정 저장 (비밀번호 제외)
    save_crawler_config(config)

    # 백그라운드에서 크롤링 실행
    thread = threading.Thread(target=run_crawler_task, args=(config, password))
    thread.daemon = True
    thread.start()

    flash('크롤링이 시작되었습니다. 브라우저에서 로그인해주세요.', 'success')
    return redirect(url_for('index'))


@app.route('/crawl/status')
def get_crawl_status():
    """크롤링 상태 조회"""
    return jsonify(crawl_status)


# ===== QA 추출 =====

@app.route('/extract', methods=['POST'])
def extract_qa():
    """CSV 파일에서 QA 추출"""
    try:
        selected_files = request.form.getlist('files')

        if not selected_files:
            flash('파일을 선택해주세요.', 'error')
            return redirect(url_for('qa_page'))

        extractor = QAExtractor()
        all_qa_items = []

        for filename in selected_files:
            filepath = OUTPUT_DIR / filename
            if filepath.exists():
                logger.info(f"QA 추출 중: {filename}")
                qa_items = extractor.extract_from_csv(str(filepath))
                all_qa_items.extend(qa_items)

        if not all_qa_items:
            flash('추출된 QA가 없습니다. 질문 형식의 게시글이 없을 수 있습니다.', 'warning')
            return redirect(url_for('qa_page'))

        # ID 재할당
        for i, item in enumerate(all_qa_items, 1):
            item.id = i

        # 결과 저장
        result_path = extractor.save_qa_csv(all_qa_items)

        if result_path:
            flash(f'QA 추출 완료: {len(all_qa_items)}개 항목이 생성되었습니다.', 'success')
        else:
            flash('QA 저장에 실패했습니다.', 'error')

    except Exception as e:
        logger.error(f"QA 추출 오류: {e}")
        flash(f'오류 발생: {str(e)}', 'error')

    return redirect(url_for('qa_page'))


# ===== 파일 관리 =====

@app.route('/upload', methods=['POST'])
def upload_file():
    """CSV 파일 업로드"""
    if 'file' not in request.files:
        flash('파일이 선택되지 않았습니다.', 'error')
        return redirect(url_for('qa_page'))

    file = request.files['file']
    if file.filename == '':
        flash('파일이 선택되지 않았습니다.', 'error')
        return redirect(url_for('qa_page'))

    if not file.filename.endswith('.csv'):
        flash('CSV 파일만 업로드할 수 있습니다.', 'error')
        return redirect(url_for('qa_page'))

    try:
        filepath = OUTPUT_DIR / file.filename
        file.save(str(filepath))
        flash(f'파일 업로드 완료: {file.filename}', 'success')
    except Exception as e:
        logger.error(f"파일 업로드 실패: {e}")
        flash(f'업로드 실패: {str(e)}', 'error')

    return redirect(url_for('qa_page'))


@app.route('/download/<filename>')
def download_file(filename):
    """파일 다운로드"""
    filepath = OUTPUT_DIR / filename
    if filepath.exists():
        return send_file(
            str(filepath),
            as_attachment=True,
            download_name=filename
        )
    flash('파일을 찾을 수 없습니다.', 'error')
    return redirect(url_for('index'))


@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    """파일 삭제"""
    filepath = OUTPUT_DIR / filename
    if filepath.exists():
        filepath.unlink()
        flash(f'파일 삭제 완료: {filename}', 'success')
    else:
        flash('파일을 찾을 수 없습니다.', 'error')

    # 리퍼러에 따라 리다이렉트
    referer = request.headers.get('Referer', '')
    if 'qa' in referer:
        return redirect(url_for('qa_page'))
    return redirect(url_for('index'))


# ===== 제외 키워드 =====

@app.route('/keywords/add', methods=['POST'])
def add_keyword_form():
    """폼을 통한 키워드 추가"""
    keyword = request.form.get('keyword', '').strip()

    if not keyword:
        flash('키워드를 입력해주세요.', 'error')
    elif exclude_keywords_manager.add_keyword(keyword):
        flash(f'제외 키워드 추가: {keyword}', 'success')
    else:
        flash('이미 등록된 키워드입니다.', 'warning')

    referer = request.headers.get('Referer', '')
    if 'settings' in referer:
        return redirect(url_for('settings_page'))
    return redirect(url_for('index'))


@app.route('/keywords/remove/<keyword>', methods=['POST'])
def remove_keyword_form(keyword):
    """폼을 통한 키워드 삭제"""
    if exclude_keywords_manager.remove_keyword(keyword):
        flash(f'제외 키워드 삭제: {keyword}', 'success')
    else:
        flash('키워드를 찾을 수 없습니다.', 'error')

    referer = request.headers.get('Referer', '')
    if 'settings' in referer:
        return redirect(url_for('settings_page'))
    return redirect(url_for('index'))


@app.route('/keywords/clear', methods=['POST'])
def clear_keywords():
    """모든 제외 키워드 삭제"""
    exclude_keywords_manager.clear_keywords()
    flash('모든 제외 키워드가 삭제되었습니다.', 'success')

    referer = request.headers.get('Referer', '')
    if 'settings' in referer:
        return redirect(url_for('settings_page'))
    return redirect(url_for('index'))


# ===== API =====

@app.route('/api/keywords', methods=['GET'])
def api_get_keywords():
    """제외 키워드 목록 조회"""
    return jsonify({
        'success': True,
        'keywords': exclude_keywords_manager.get_keywords()
    })


@app.route('/api/keywords', methods=['POST'])
def api_add_keyword():
    """제외 키워드 추가"""
    data = request.get_json()
    keyword = data.get('keyword', '').strip()

    if not keyword:
        return jsonify({'success': False, 'message': '키워드를 입력해주세요.'})

    if exclude_keywords_manager.add_keyword(keyword):
        return jsonify({
            'success': True,
            'message': f'키워드 추가됨: {keyword}',
            'keywords': exclude_keywords_manager.get_keywords()
        })
    else:
        return jsonify({
            'success': False,
            'message': '이미 등록된 키워드입니다.'
        })


@app.route('/api/files', methods=['GET'])
def api_list_files():
    """CSV 파일 목록 API"""
    csv_files, qa_files = get_file_list()
    return jsonify({
        'success': True,
        'csv_files': csv_files,
        'qa_files': qa_files
    })


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("네이버 카페 크롤러 웹 앱")
    print("=" * 50)
    print(f"출력 디렉토리: {OUTPUT_DIR}")
    print(f"제외 키워드: {exclude_keywords_manager.get_keywords()}")
    print("=" * 50)
    print("http://localhost:5555 에서 접속하세요")
    print("=" * 50 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5555)
