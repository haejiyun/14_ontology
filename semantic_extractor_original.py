#!/usr/bin/env python3
"""
Tiny Mall 상품 의미 추출기 (용도/상황 키워드 발굴)
================================================

tiny-mall.db의 비정형 텍스트(상품명, 설명)에서
'용도'(purpose)와 '상황'(situation) 키워드를 추출하는 도구입니다.

추출 전략:
    1. 상품명에서 정규식으로 옵션 파싱 (색상, 용량, 세대, 모델 등)
    2. 설명이 부족한 경우 SearXNG에서 보충 텍스트 수집
    3. Ollama LLM으로 용도/상황 키워드 추출
    4. 결과를 JSON 파일로 저장

사용법:
    python semantic_extractor.py
    python semantic_extractor.py --limit 5
    python semantic_extractor.py --db-path /path/to/tiny_mall.db
    TINY_MALL_DB=/path/to/db.db python semantic_extractor.py

필요 사항:
    1. Ollama 실행: ollama serve
    2. 모델 다운로드: ollama pull qwen2.5:3b
    3. SearXNG 실행: searxng docker 또는 로컬 설치
"""

import argparse
import json
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


# ============================================================================
# 설정
# ============================================================================

# SearXNG 검색 엔진 설정
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8888/search")

# Ollama LLM 모델 설정
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# 출력 디렉토리 설정
OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "semantic_keywords.json"

# API 요청 딜레이 (과부하 방지)
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "2.0"))

# 색상 키워드 목록 (정규식 매칭용)
COLOR_KEYWORDS = [
    "베이지", "블랙", "화이트", "실버", "그라파이트",
    "그레이", "검정", "회색", "흰색", "검은색",
    "블루", "핑크", "그린", "골드", "로즈",
    "미스틱 실버", "미스틱 블랙", "스타라이트",
]

# 저장 용량 패턴 (GB/TB 용량 인식)
STORAGE_PATTERN = r'(\d+(?:\.\d+)?\s*(?:GB|TB|MB))'

# 세대 패턴 (예: 16세대, M1, M2)
GENERATION_PATTERN = r'(M\d+|M\d+\s*Pro|Max|Ultra|\d+(?:세대|th gen|gen\d))'


# ============================================================================
# 1단계: 데이터 로드
# ============================================================================

def get_db_path() -> str:
    """
    데이터베이스 경로를 결정합니다

    우선순위:
        1. 환경 변수: TINY_MALL_DB
        2. 상대 경로: ../tiny-mall/db/tiny_mall.db
        3. 현재 디렉토리: ./tiny_mall.db

    Returns:
        str: 데이터베이스 파일 경로
    """
    # 환경 변수 확인
    if os.getenv("TINY_MALL_DB"):
        return os.getenv("TINY_MALL_DB")

    # 상대 경로 확인
    relative_path = Path(__file__).parent.parent / "tiny-mall" / "db" / "tiny_mall.db"
    if relative_path.exists():
        return str(relative_path.resolve())

    # 현재 디렉토리 확인
    if Path("./tiny_mall.db").exists():
        return "./tiny_mall.db"

    # 기본값 (존재하지 않을 수 있음)
    return "../tiny-mall/db/tiny_mall.db"


def load_products(db_path: str, limit: int = 0) -> List[Dict]:
    """
    SQLite 데이터베이스에서 상품 목록을 로드합니다

    Args:
        db_path (str): 데이터베이스 파일 경로
        limit (int): 로드할 상품 수 제한 (0=전체)

    Returns:
        List[Dict]: 상품 정보 딕셔너리 목록
            각 항목: {id, name, description, price, image_url, ...}

    Raises:
        FileNotFoundError: DB 파일이 없을 경우
        sqlite3.Error: DB 접근 오류
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(f"데이터베이스 파일을 찾을 수 없습니다: {db_path}")

    # DB 연결
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 상품 정보 쿼리
    # product_attributes와 reviews도 함께 가져오면 더 풍부한 정보 제공 가능
    cursor.execute("""
        SELECT
            id, name, description, price, image_url,
            created_at, updated_at
        FROM products
        ORDER BY id
    """)

    # 모든 행을 딕셔너리로 변환
    products = [dict(row) for row in cursor.fetchall()]

    # 개수 제한 적용
    if limit > 0:
        products = products[:limit]

    conn.close()
    return products


def load_product_attributes(db_path: str, product_id: int) -> List[Dict]:
    """
    특정 상품의 속성 정보를 로드합니다

    Args:
        db_path (str): 데이터베이스 파일 경로
        product_id (int): 상품 ID

    Returns:
        List[Dict]: 속성 목록
            각 항목: {attribute_name, attribute_value}
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT attribute_name, attribute_value
        FROM product_attributes
        WHERE product_id = ?
        ORDER BY sort_order, id
    """, (product_id,))

    attributes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return attributes


# ============================================================================
# 2단계: 상품명 옵션 파싱
# ============================================================================

def parse_product_name(name: str) -> Dict:
    """
    상품명에서 괄호 안의 옵션(색상, 용량, 세대 등)을 파싱합니다

    예시:
        "아이폰 16 (검정, 256GB)" → {color: "검정", storage: "256GB"}
        "맥북 프로 (M4 Pro, 32GB)" → {generation: "M4 Pro"}

    Args:
        name (str): 상품명

    Returns:
        Dict: 파싱된 옵션
            {
                'raw_options': [괄호 내용들],
                'color': '색상명' or None,
                'storage': '용량' or None,
                'generation': '세대' or None,
                'model': '모델명' or None
            }
    """
    # 괄호 안 내용 추출 (다양한 괄호 타입 지원)
    raw_options = re.findall(r'[\(（\[]([^)）\]]+)[\)）\]]', name)

    # 각 괄호 내용을 쉼표로 분리
    values = []
    for opt in raw_options:
        values.extend([v.strip() for v in opt.split(",") if v.strip()])

    result = {
        'raw_options': raw_options,
        'color': None,
        'storage': None,
        'generation': None,
        'model': None,
    }

    # 색상 매칭 (색상 키워드 사전 사용)
    for v in values:
        for keyword in COLOR_KEYWORDS:
            if keyword.lower() in v.lower():
                result['color'] = keyword
                break
        if result['color']:
            break

    # 용량 매칭 (GB/TB 패턴)
    for v in values:
        match = re.search(STORAGE_PATTERN, v, re.IGNORECASE)
        if match:
            result['storage'] = match.group(1)
            break

    # 세대/모델 매칭 (M1, M2, Intel 등)
    for v in values:
        match = re.search(GENERATION_PATTERN, v)
        if match:
            result['generation'] = match.group(1)
            break

    # 추가: 모델명 (기타 정보)
    if not result['generation'] and values:
        # 색상, 용량이 아닌 첫 번째 값을 모델명으로 간주
        for v in values:
            if v != result['color'] and v != result['storage']:
                result['model'] = v
                break

    return result


# ============================================================================
# 3단계: 보충 필요 여부 판단
# ============================================================================

def needs_supplement(product: Dict, min_length: int = 50) -> bool:
    """
    상품의 설명이 충분한지 판단합니다

    설명이 없거나 최소 길이 미만이면 보충 수집이 필요합니다.

    Args:
        product (Dict): 상품 정보
        min_length (int): 충분한 설명의 최소 길이 (기본값: 50자)

    Returns:
        bool: True if 보충 필요, False if 충분함
    """
    description = product.get("description")

    if not description:
        return True

    # 공백/줄바꿈 제거 후 길이 확인
    cleaned = description.strip()
    return len(cleaned) < min_length


# ============================================================================
# 4단계: SearXNG 보충 수집
# ============================================================================

def supplement_with_searxng(
    product_name: str,
    timeout: int = 10,
    max_results: int = 3
) -> str:
    """
    SearXNG 검색 엔진에서 용도/상황 관련 텍스트를 보충 수집합니다

    SearXNG가 실행 중이지 않으면 빈 문자열을 반환합니다.
    상품에 대한 추가 정보를 검색하여 용도와 상황 추출에 활용합니다.

    Args:
        product_name (str): 상품명
        timeout (int): HTTP 요청 타임아웃 (초)
        max_results (int): 수집할 최대 검색 결과 수

    Returns:
        str: 보충된 텍스트 (검색 결과 내용 연결)
    """
    # 용도와 상황을 포함한 검색 쿼리 작성
    query = f"{product_name} 용도 추천 사용처 상황"

    params = {
        "q": query,
        "format": "json",
        "language": "ko"
    }

    try:
        # SearXNG API 호출
        response = requests.get(
            SEARXNG_URL,
            params=params,
            timeout=timeout
        )
        response.raise_for_status()

        # JSON 응답 파싱
        data = response.json()
        results = data.get("results", [])[:max_results]

        # 검색 결과에서 텍스트 추출
        texts = [
            r.get("content", "")
            for r in results
            if r.get("content")
        ]

        # 여러 텍스트 연결
        supplemented = " ".join(texts)
        return supplemented

    except requests.exceptions.ConnectionError:
        # SearXNG 서버에 연결할 수 없음
        return ""
    except requests.exceptions.Timeout:
        # 요청 타임아웃
        return ""
    except Exception:
        # 기타 오류
        return ""


# ============================================================================
# 5단계: LLM을 사용한 의미 키워드 추출
# ============================================================================

def extract_keywords_with_llm(product: Dict) -> Dict:
    """
    Ollama LLM을 사용하여 상품의 용도와 상황 키워드를 추출합니다

    Ollama가 실행 중이지 않으면 빈 결과를 반환합니다.

    Args:
        product (Dict): 상품 정보
            필드: name, description, extra_text(선택), attributes(선택)

    Returns:
        Dict: 추출된 키워드
            {
                'purpose': ['용도1', '용도2', ...],
                'situation': ['상황1', '상황2', ...],
                'keywords': ['종합키워드1', ...]
            }
    """
    if not OLLAMA_AVAILABLE:
        # ollama 라이브러리가 설치되지 않았음
        return {
            "purpose": [],
            "situation": [],
            "keywords": []
        }

    # 상품 정보 수집
    name = product.get("name", "")
    description = product.get("description", "") or ""
    extra_text = product.get("extra_text", "") or ""
    attributes = product.get("attributes", [])

    # 텍스트 블록 구성
    text_block = f"상품명: {name}\n설명: {description}"

    if attributes:
        attr_str = ", ".join(
            f"{a['attribute_name']}={a['attribute_value']}"
            for a in attributes
        )
        text_block += f"\n속성: {attr_str}"

    if extra_text:
        text_block += f"\n추가정보: {extra_text}"

    # LLM 프롬프트 작성
    prompt = f"""당신은 전자제품 및 소비재 전문가입니다.
아래 상품 정보를 읽고, 이 상품의 '용도(purpose)', '상황(situation)',
그리고 종합 의미 '키워드(keywords)'를 추출하세요.

{text_block}

## 추출 규칙
- 용도: 이 상품이 사용되는 목적 (예: 영상편집, 학습용, 업무용, 게이밍)
- 상황: 이 상품이 사용되는 장소나 환경 (예: 재택, 카페, 이동중, 출장)
- 키워드: 상품의 특성을 나타내는 종합 키워드 (예: 고성능, 휴대용, 대화면)
- 각 카테고리마다 3~5개의 키워드를 추출하세요
- JSON 형식으로만 응답하세요

## 응답 형식
{{
  "purpose": ["용도1", "용도2", ...],
  "situation": ["상황1", "상황2", ...],
  "keywords": ["키워드1", "키워드2", ...]
}}

## 응답 (JSON만 출력)"""

    try:
        # Ollama API 호출
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1}  # 낮은 온도로 일관성 있는 응답
        )

        # 응답 추출 및 JSON 파싱
        raw_response = response["message"]["content"].strip()
        return _parse_json_response(raw_response)

    except Exception:
        # Ollama 서버 연결 실패 등의 오류
        return {
            "purpose": [],
            "situation": [],
            "keywords": []
        }


def _parse_json_response(raw: str) -> Dict:
    """
    LLM 응답에서 JSON을 안전하게 파싱합니다

    마크다운 코드 펜스, 추가 텍스트 등을 처리합니다.

    Args:
        raw (str): LLM의 원본 응답

    Returns:
        Dict: 파싱된 JSON 데이터 (또는 기본값)
    """
    fallback = {
        "purpose": [],
        "situation": [],
        "keywords": []
    }

    # 마크다운 코드 펜스 제거
    clean = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    # 중괄호 블록만 추출
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        clean = match.group(0)

    try:
        # JSON 파싱
        data = json.loads(clean)

        # 필드 검증
        return {
            "purpose": data.get("purpose", []),
            "situation": data.get("situation", []),
            "keywords": data.get("keywords", [])
        }
    except json.JSONDecodeError:
        # JSON 파싱 실패
        return fallback


# ============================================================================
# 6단계: 결과 저장
# ============================================================================

def save_results(results: List[Dict], output_path: Path) -> None:
    """
    추출 결과를 JSON 파일로 저장하고 통계를 출력합니다

    Args:
        results (List[Dict]): 추출 결과 목록
        output_path (Path): 출력 파일 경로
    """
    # 출력 디렉토리 생성
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # JSON으로 저장
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 통계 계산
    total = len(results)
    with_purpose = sum(1 for r in results if r.get("purpose"))
    with_situation = sum(1 for r in results if r.get("situation"))
    with_keywords = sum(1 for r in results if r.get("keywords"))
    supplemented = sum(1 for r in results if r.get("supplemented"))

    # 통계 출력
    print("\n" + "=" * 70)
    print("추출 완료")
    print("=" * 70)
    print(f"저장 위치: {output_path}")
    print(f"\n통계:")
    print(f"  총 상품 수:        {total}")
    print(f"  용도 추출 성공:    {with_purpose}/{total} ({100*with_purpose//total if total else 0}%)")
    print(f"  상황 추출 성공:    {with_situation}/{total} ({100*with_situation//total if total else 0}%)")
    print(f"  키워드 추출 성공:  {with_keywords}/{total} ({100*with_keywords//total if total else 0}%)")
    print(f"  보충 수집 사용:    {supplemented}/{total} ({100*supplemented//total if total else 0}%)")


# ============================================================================
# 7단계: 메인 오케스트레이션
# ============================================================================

def main() -> None:
    """
    메인 실행 함수

    1. 명령행 인자 파싱
    2. 상품 데이터 로드
    3. 각 상품별로 의미 추출 수행
    4. 결과 저장
    """
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(
        description="상품 텍스트 의미 추출기 (용도/상황 키워드 발굴)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="처리할 상품 수 제한 (0=전체, 기본값: 0)"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        help="SQLite DB 파일 경로 (생략 시 자동 감지)"
    )
    parser.add_argument(
        "--searxng",
        type=str,
        default=SEARXNG_URL,
        help=f"SearXNG URL (기본값: {SEARXNG_URL})"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=OLLAMA_MODEL,
        help=f"Ollama 모델 (기본값: {OLLAMA_MODEL})"
    )

    args = parser.parse_args()

    # 설정값 결정
    db_path = args.db_path or get_db_path()
    limit = args.limit
    searxng_url = args.searxng
    ollama_model = args.model

    # 헤더 출력
    print("=" * 70)
    print("Tiny Mall 상품 의미 추출기")
    print("=" * 70)
    print(f"DB 경로:        {db_path}")
    print(f"LLM 모델:       {ollama_model}")
    print(f"SearXNG:        {searxng_url}")
    print(f"처리 한계:      {limit if limit > 0 else '무제한'}")
    print()

    # DB 파일 확인
    if not Path(db_path).exists():
        print(f"오류: 데이터베이스를 찾을 수 없습니다: {db_path}")
        print("\nDB 경로 지정 방법:")
        print("  1. 명령행: python semantic_extractor.py --db-path /path/to/db")
        print("  2. 환경변수: export TINY_MALL_DB=/path/to/db")
        print("  3. 상대경로: ../tiny-mall/db/tiny_mall.db")
        return

    # 1단계: 상품 로드
    try:
        products = load_products(db_path, limit)
    except Exception as e:
        print(f"오류: 상품 로드 실패 - {e}")
        return

    print(f"로드된 상품: {len(products)}건")
    print("-" * 70)

    # Ollama 가용성 확인
    if not OLLAMA_AVAILABLE:
        print("경고: ollama 라이브러리가 설치되지 않았습니다")
        print("  설치: pip install ollama")

    # 결과 저장소
    results = []

    # 2~5단계: 각 상품 처리
    for idx, product in enumerate(products, 1):
        name = product["name"]
        product_id = product["id"]

        print(f"\n[{idx}/{len(products)}] {name}")

        # 상품명 파싱
        parsed = parse_product_name(name)
        if parsed["color"] or parsed["storage"] or parsed["generation"]:
            opts = []
            if parsed["color"]:
                opts.append(f"색상={parsed['color']}")
            if parsed["storage"]:
                opts.append(f"용량={parsed['storage']}")
            if parsed["generation"]:
                opts.append(f"세대={parsed['generation']}")
            print(f"  옵션: {', '.join(opts)}")

        # 속성 정보 로드
        attributes = load_product_attributes(db_path, product_id)
        if attributes:
            print(f"  속성: {len(attributes)}개")

        # SearXNG 보충 수집 여부 판단
        extra_text = ""
        supplemented = False

        if needs_supplement(product):
            print(f"  설명 부족 → SearXNG 보충 수집 중...")
            extra_text = supplement_with_searxng(name)
            supplemented = bool(extra_text)

            if supplemented:
                print(f"  보충됨: {len(extra_text)}자")
            else:
                print(f"  보충 실패 (SearXNG 미응답)")

            time.sleep(REQUEST_DELAY)
        else:
            print(f"  설명 충분 (길이: {len(product.get('description', ''))}자)")

        # LLM 키워드 추출
        print(f"  LLM 추출 중...")
        product_data = {
            **product,
            "extra_text": extra_text,
            "attributes": attributes
        }
        keywords = extract_keywords_with_llm(product_data)

        # 추출 결과 출력
        if keywords["purpose"]:
            print(f"    용도: {', '.join(keywords['purpose'])}")
        if keywords["situation"]:
            print(f"    상황: {', '.join(keywords['situation'])}")
        if keywords["keywords"]:
            print(f"    키워드: {', '.join(keywords['keywords'])}")

        # 결과 저장
        result = {
            "product_id": product_id,
            "name": name,
            "price": product.get("price"),
            "parsed_options": parsed,
            "original_description": product.get("description") or "",
            "attributes": attributes,
            "supplemented": supplemented,
            "extra_text": extra_text,
            "purpose": keywords.get("purpose", []),
            "situation": keywords.get("situation", []),
            "keywords": keywords.get("keywords", []),
            "extracted_at": datetime.now().isoformat()
        }
        results.append(result)

        time.sleep(REQUEST_DELAY)

    # 6단계: 결과 저장
    save_results(results, OUTPUT_FILE)


if __name__ == "__main__":
    main()
