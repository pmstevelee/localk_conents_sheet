"""
QA 추출기
크롤링된 카페 게시글에서 질문과 답변을 추출하여 정리
저작권을 고려하여 커뮤니티 말투를 유지하면서 재구성
"""
import csv
import re
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.settings import OUTPUT_DIR

logger = logging.getLogger(__name__)


@dataclass
class QAItem:
    """질문-답변 아이템"""
    id: int
    subject: str  # 질문 제목
    question: str  # 질문 본문
    answer1: str = ""
    answer2: str = ""
    answer3: str = ""
    category: str = "life"
    keywords: str = ""
    source: str = "custom"
    region: str = "halifax"


class QAExtractor:
    """
    크롤링된 CSV에서 질문-답변을 추출하는 클래스
    """

    # 질문 패턴 (제목에서 질문 식별)
    QUESTION_PATTERNS = [
        r'[?？]',  # 물음표
        r'질문',
        r'궁금',
        r'어떻게',
        r'어디서',
        r'언제',
        r'누가',
        r'무엇',
        r'뭐',
        r'왜',
        r'어떤',
        r'얼마',
        r'도움',
        r'알려주',
        r'추천',
        r'조언',
        r'문의',
        r'여쭤',
        r'여쭙',
        r'~요\?',
        r'~까요',
        r'~나요',
        r'~ㄹ까요',
        r'~할까요',
        r'~인가요',
        r'~던가요',
        r'~ㄴ가요',
        r'~죠\?',
    ]

    # 카테고리 키워드 매핑
    CATEGORY_KEYWORDS = {
        'immigration': ['이민', '비자', 'visa', '영주권', 'pr', 'lmia', '워크퍼밋', '워홀', '이민자', '신청', '서류'],
        'housing': ['집', '렌트', 'rent', '아파트', '콘도', '주거', '월세', '전세', '부동산', '이사', '방'],
        'job': ['취업', '직장', '일자리', '잡', 'job', '면접', '이력서', '근무', '회사', '급여', '연봉'],
        'education': ['학교', '대학', '교육', '공부', '학원', '수업', '과외', '자녀', '아이', '학비', '유학'],
        'health': ['병원', '의료', '건강', '의사', '약', '보험', '진료', '치료', '아프', '증상'],
        'finance': ['세금', '은행', '돈', '송금', '환전', '계좌', '카드', 'tax', '금융', '대출'],
        'shopping': ['쇼핑', '마트', '한인마트', '구매', '물건', '가격', '어디서', '파는'],
        'transportation': ['차', '자동차', '운전', '면허', '보험', '대중교통', '버스', '택시'],
        'food': ['음식', '식당', '맛집', '요리', '레시피', '한식', '먹을'],
        'life': [],  # 기본 카테고리
    }

    # 지역 키워드 매핑
    REGION_KEYWORDS = {
        'halifax': ['핼리팩스', 'halifax', '핼팩', 'ns', '노바스코샤', 'nova scotia', '다트머스', 'dartmouth'],
        'toronto': ['토론토', 'toronto', 'gta', 'on', '온타리오'],
        'vancouver': ['밴쿠버', 'vancouver', 'bc', '브리티시컬럼비아'],
        'calgary': ['캘거리', 'calgary', 'ab', '알버타'],
        'montreal': ['몬트리올', 'montreal', 'qc', '퀘벡'],
        'edmonton': ['에드먼턴', 'edmonton'],
        'winnipeg': ['위니펙', 'winnipeg', 'mb', '매니토바'],
        'ottawa': ['오타와', 'ottawa'],
    }

    def __init__(self, output_dir: str = None):
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.qa_items: List[QAItem] = []
        self.id_counter = 1

    def load_csv(self, filepath: str) -> List[Dict]:
        """
        크롤링된 CSV 파일 로드

        Args:
            filepath: CSV 파일 경로

        Returns:
            게시글/댓글 데이터 리스트
        """
        posts_data = []

        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    posts_data.append(row)
            logger.info(f"CSV 로드 완료: {filepath} ({len(posts_data)}행)")
        except Exception as e:
            logger.error(f"CSV 로드 실패: {e}")

        return posts_data

    def group_by_post(self, rows: List[Dict]) -> Dict[str, Dict]:
        """
        게시글ID별로 데이터 그룹화

        Args:
            rows: CSV 행 데이터

        Returns:
            {게시글ID: {post_info, comments: []}} 형태
        """
        grouped = {}

        for row in rows:
            post_id = row.get('게시글ID', '')
            if not post_id:
                continue

            if post_id not in grouped:
                grouped[post_id] = {
                    'id': post_id,
                    'title': row.get('제목', ''),
                    'author': row.get('작성자', ''),
                    'date': row.get('작성일', ''),
                    'content': row.get('본문내용', ''),
                    'view_count': row.get('조회수', '0'),
                    'like_count': row.get('좋아요수', '0'),
                    'url': row.get('URL', ''),
                    'comments': []
                }

            # 댓글 정보 추가
            comment_author = row.get('댓글작성자', '')
            comment_content = row.get('댓글내용', '')
            if comment_author and comment_content:
                grouped[post_id]['comments'].append({
                    'author': comment_author,
                    'content': comment_content,
                    'date': row.get('댓글작성일', ''),
                    'is_reply': row.get('대댓글여부', '') == '대댓글'
                })

        return grouped

    def is_question_post(self, post: Dict) -> bool:
        """
        질문 게시글인지 판별

        Args:
            post: 게시글 데이터

        Returns:
            질문 여부
        """
        title = post.get('title', '').lower()
        content = post.get('content', '').lower()
        text = f"{title} {content}"

        for pattern in self.QUESTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def detect_category(self, text: str) -> str:
        """
        텍스트에서 카테고리 감지

        Args:
            text: 분석할 텍스트

        Returns:
            카테고리명
        """
        text_lower = text.lower()

        category_scores = defaultdict(int)

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    category_scores[category] += 1

        if category_scores:
            return max(category_scores, key=category_scores.get)

        return 'life'

    def detect_region(self, text: str) -> str:
        """
        텍스트에서 지역 감지

        Args:
            text: 분석할 텍스트

        Returns:
            지역명
        """
        text_lower = text.lower()

        for region, keywords in self.REGION_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return region

        return 'halifax'  # 기본값

    def extract_keywords(self, text: str, max_keywords: int = 5) -> str:
        """
        텍스트에서 키워드 추출

        Args:
            text: 분석할 텍스트
            max_keywords: 최대 키워드 수

        Returns:
            쉼표로 구분된 키워드
        """
        # 명사 추출을 위한 간단한 패턴 (더 정교한 처리가 필요하면 konlpy 등 사용)
        # 여기서는 기본적인 키워드 추출
        keywords = []

        # 카테고리 키워드에서 매칭되는 것 찾기
        text_lower = text.lower()
        for category, cat_keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in cat_keywords:
                if keyword.lower() in text_lower and keyword not in keywords:
                    keywords.append(keyword)
                    if len(keywords) >= max_keywords:
                        break
            if len(keywords) >= max_keywords:
                break

        return ','.join(keywords)

    def score_answer(self, comment: Dict, question_text: str) -> Tuple[int, str]:
        """
        답변의 품질 점수 계산

        Args:
            comment: 댓글 데이터
            question_text: 질문 텍스트

        Returns:
            (점수, 답변 유형)
        """
        content = comment.get('content', '')
        score = 0
        answer_type = 'opinion'  # 의견

        # 길이 점수 (너무 짧으면 감점, 적당하면 가점)
        length = len(content)
        if length < 10:
            score -= 5
        elif length > 30:
            score += 2
        if length > 100:
            score += 3

        # 정보성 키워드
        info_keywords = ['있어요', '있습니다', '해요', '합니다', '됩니다', '되요',
                        '하면', '가면', '이용', '추천', '경험', '알려', '정보',
                        '연락처', '번호', '주소', '가격', '비용', '시간', '방법']
        for keyword in info_keywords:
            if keyword in content:
                score += 2
                answer_type = 'informative'

        # 공감성 키워드
        empathy_keywords = ['공감', '응원', '화이팅', '힘내', '이해', '걱정',
                           '좋겠', '바랍니다', '바라요', '축하', '잘될']
        for keyword in empathy_keywords:
            if keyword in content:
                score += 1
                if answer_type != 'informative':
                    answer_type = 'empathy'

        # 링크가 있으면 정보성 가점
        if 'http' in content or 'www' in content:
            score += 3
            answer_type = 'informative'

        # 대댓글이면 약간 감점 (직접 답변 우선)
        if comment.get('is_reply'):
            score -= 1

        return score, answer_type

    def select_best_answers(self, comments: List[Dict], question_text: str, max_answers: int = 3) -> List[str]:
        """
        최적의 답변 선택

        Args:
            comments: 댓글 리스트
            question_text: 질문 텍스트
            max_answers: 최대 답변 수

        Returns:
            선택된 답변 리스트
        """
        if not comments:
            return []

        # 각 댓글 점수 계산
        scored_comments = []
        for comment in comments:
            score, answer_type = self.score_answer(comment, question_text)
            scored_comments.append({
                'content': comment.get('content', ''),
                'score': score,
                'type': answer_type
            })

        # 점수 기준 정렬
        scored_comments.sort(key=lambda x: x['score'], reverse=True)

        # 정보성 답변 우선, 없으면 공감/의견 답변 채택
        informative = [c for c in scored_comments if c['type'] == 'informative']
        empathy = [c for c in scored_comments if c['type'] == 'empathy']
        opinion = [c for c in scored_comments if c['type'] == 'opinion']

        selected = []

        # 정보성 답변 먼저
        for c in informative[:max_answers]:
            selected.append(c['content'])

        # 부족하면 공감 답변
        remaining = max_answers - len(selected)
        if remaining > 0:
            for c in empathy[:remaining]:
                selected.append(c['content'])

        # 그래도 부족하면 의견 답변
        remaining = max_answers - len(selected)
        if remaining > 0:
            for c in opinion[:remaining]:
                if c['score'] > 0:  # 점수가 양수인 것만
                    selected.append(c['content'])

        return selected[:max_answers]

    def rephrase_content(self, text: str, is_question: bool = True) -> str:
        """
        내용 재구성 (저작권 고려, 커뮤니티 말투 유지)

        실제 구현에서는 더 정교한 재구성 로직 필요
        여기서는 기본적인 정리만 수행

        Args:
            text: 원본 텍스트
            is_question: 질문인지 여부

        Returns:
            재구성된 텍스트
        """
        if not text:
            return ""

        # 기본 정리
        result = text.strip()

        # 과도한 공백 제거
        result = re.sub(r'\s+', ' ', result)

        # 불필요한 인사말 제거 (질문 앞의 인사말)
        if is_question:
            greeting_patterns = [
                r'^안녕하세요[.!?\s]*',
                r'^안녕하세요[,]\s*',
                r'^반갑습니다[.!?\s]*',
                r'^처음\s*글\s*올립니다[.!?\s]*',
            ]
            for pattern in greeting_patterns:
                result = re.sub(pattern, '', result, flags=re.IGNORECASE)

        # 과도한 이모티콘/특수문자 정리
        result = re.sub(r'[ㅋㅎㅠㅜ]{3,}', '', result)
        result = re.sub(r'[!?]{3,}', '?', result)
        result = re.sub(r'\.{3,}', '...', result)

        return result.strip()

    def process_post(self, post: Dict) -> Optional[QAItem]:
        """
        게시글을 QA 아이템으로 변환

        Args:
            post: 게시글 데이터

        Returns:
            QAItem 또는 None
        """
        if not self.is_question_post(post):
            return None

        title = post.get('title', '')
        content = post.get('content', '')
        comments = post.get('comments', [])

        # 답변이 없는 질문은 스킵
        if not comments:
            return None

        # 텍스트 재구성
        subject = self.rephrase_content(title, is_question=True)
        question = self.rephrase_content(content, is_question=True)

        # 답변 선택
        answers = self.select_best_answers(comments, f"{title} {content}")

        # 답변이 없으면 스킵
        if not answers:
            return None

        # 답변 재구성
        rephrased_answers = [self.rephrase_content(a, is_question=False) for a in answers]

        # 카테고리/지역/키워드 감지
        full_text = f"{title} {content}"
        category = self.detect_category(full_text)
        region = self.detect_region(full_text)
        keywords = self.extract_keywords(full_text)

        qa_item = QAItem(
            id=self.id_counter,
            subject=subject,
            question=question,
            answer1=rephrased_answers[0] if len(rephrased_answers) > 0 else "",
            answer2=rephrased_answers[1] if len(rephrased_answers) > 1 else "",
            answer3=rephrased_answers[2] if len(rephrased_answers) > 2 else "",
            category=category,
            keywords=keywords,
            source='custom',
            region=region
        )

        self.id_counter += 1
        return qa_item

    def extract_from_csv(self, filepath: str) -> List[QAItem]:
        """
        CSV 파일에서 QA 추출

        Args:
            filepath: CSV 파일 경로

        Returns:
            QAItem 리스트
        """
        rows = self.load_csv(filepath)
        grouped = self.group_by_post(rows)

        qa_items = []
        for post_id, post in grouped.items():
            qa_item = self.process_post(post)
            if qa_item:
                qa_items.append(qa_item)

        logger.info(f"QA 추출 완료: {len(qa_items)}개")
        return qa_items

    def save_qa_csv(self, qa_items: List[QAItem], filename: str = None) -> str:
        """
        QA 아이템을 CSV로 저장

        Args:
            qa_items: QAItem 리스트
            filename: 출력 파일명

        Returns:
            저장된 파일 경로
        """
        if not qa_items:
            logger.warning("저장할 QA 항목이 없습니다.")
            return ""

        if not filename:
            today = datetime.now().strftime("%Y%m%d")
            filename = f"qa_extracted_{today}.csv"

        filepath = self.output_dir / filename

        headers = ['id', 'subject', 'question', 'answer1', 'answer2', 'answer3',
                   'category', 'keywords', 'source', 'region']

        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(headers)

                for item in qa_items:
                    row = [
                        item.id,
                        item.subject,
                        item.question,
                        item.answer1,
                        item.answer2,
                        item.answer3,
                        item.category,
                        item.keywords,
                        item.source,
                        item.region
                    ]
                    writer.writerow(row)

            logger.info(f"QA CSV 저장 완료: {filepath} ({len(qa_items)}개)")
            return str(filepath)

        except Exception as e:
            logger.error(f"QA CSV 저장 실패: {e}")
            raise

    def process_directory(self, input_dir: str = None) -> str:
        """
        디렉토리 내 모든 CSV 파일 처리

        Args:
            input_dir: 입력 디렉토리 (None이면 기본 output 디렉토리)

        Returns:
            저장된 파일 경로
        """
        input_path = Path(input_dir) if input_dir else self.output_dir

        all_qa_items = []

        for csv_file in input_path.glob("*.csv"):
            # QA 결과 파일은 스킵
            if 'qa_extracted' in csv_file.name:
                continue

            logger.info(f"처리 중: {csv_file.name}")
            qa_items = self.extract_from_csv(str(csv_file))
            all_qa_items.extend(qa_items)

        # ID 재할당
        for i, item in enumerate(all_qa_items, 1):
            item.id = i

        return self.save_qa_csv(all_qa_items)


def main():
    """CLI 엔트리포인트"""
    import argparse

    parser = argparse.ArgumentParser(description='카페 게시글에서 QA 추출')
    parser.add_argument('--input', '-i', help='입력 CSV 파일 또는 디렉토리')
    parser.add_argument('--output', '-o', help='출력 디렉토리')
    parser.add_argument('--filename', '-f', help='출력 파일명')

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    extractor = QAExtractor(output_dir=args.output)

    if args.input:
        input_path = Path(args.input)
        if input_path.is_file():
            qa_items = extractor.extract_from_csv(args.input)
            result = extractor.save_qa_csv(qa_items, args.filename)
        else:
            result = extractor.process_directory(args.input)
    else:
        # 기본 output 디렉토리 처리
        result = extractor.process_directory()

    if result:
        print(f"QA 추출 완료: {result}")
    else:
        print("추출된 QA가 없습니다.")


if __name__ == '__main__':
    main()
