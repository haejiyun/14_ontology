#!/usr/bin/env python3
"""
Tiny Mall Semantic Layer
========================

목표: SQLite의 정형 데이터(DB)를 의미 있는 데이터(Semantic Layer)로 변환

학습 목표:
1. DB 스키마에서 의미 구조 파악
2. 매핑 규칙 정의 (테이블->개체, 컬럼->속성, FK->관계)
3. 데이터 변환 파이프라인 구현
4. 의미 있는 JSON 구조로 표현

Semantic Layer의 역할:
- DB를 읽기만 함 (수정 금지)
- 데이터에서 의미 추출
- 의미 있는 구조로 표현 (RDF/RDF-S 개념 차용)
"""

import sqlite3
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime


class SemanticLayer:
    """
    Semantic Layer: DB의 정형 데이터에 의미를 부여하는 계층

    이 클래스는 tiny-mall 데이터베이스의 정형 데이터를 의미론적으로 풍부한
    구조로 변환합니다. RDF(Resource Description Framework)와 같은
    의미론적 웹 기술의 개념을 따릅니다.

    역할:
    - DB 연결 및 데이터 조회
    - 의미 매핑 규칙 정의 및 관리
    - 데이터 추출 및 변환
    - 추출된 데이터 검증
    - JSON 형식의 의미 표현
    """

    def __init__(self, db_path: str):
        """
        Semantic Layer 초기화

        데이터베이스 연결을 설정하고 의미 매핑 규칙을 정의합니다.

        Args:
            db_path (str): SQLite 데이터베이스 파일의 절대 경로

        Raises:
            FileNotFoundError: DB 파일이 존재하지 않을 경우
            sqlite3.DatabaseError: DB 연결 실패 시
        """
        # 파일 존재 여부 확인
        if not Path(db_path).exists():
            raise FileNotFoundError(f"데이터베이스 파일을 찾을 수 없습니다: {db_path}")

        # DB 연결 설정
        # row_factory를 sqlite3.Row로 설정하여 컬럼 이름으로 접근 가능하게 함
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # 의미 매핑 규칙 정의
        # 이 규칙들은 DB의 물리적 구조를 의미론적 구조로 변환하는 방식을 정의합니다
        self.semantic_mappings = self._define_mappings()

    def _define_mappings(self) -> Dict[str, Any]:
        """
        Step 1: 의미 매핑 규칙 정의

        DB의 스키마를 의미 있는 개체 모델로 변환하는 규칙들을 정의합니다.

        매핑 규칙의 4가지 유형:
        1. Class Mapping: 테이블 -> 개체 유형 (Entity Type)
        2. Property Mapping: 컬럼 -> 의미 있는 속성명 (Semantic Property)
        3. Relation Mapping: 외래키/연결 테이블 -> 개체 간 관계 (Entity Relation)
        4. Rule Mapping: 데이터 제약 조건 -> 의미 규칙 (Semantic Rule)

        RDF의 개념을 활용하여:
        - 속성은 "has" 접두사 사용 (예: hasName, hasPrice)
        - 관계는 역할을 명확히 함 (예: belongsToCategory)
        - 타입 정보를 명시적으로 포함

        Returns:
            Dict[str, Any]: 의미 매핑 규칙 사전

        구조:
        {
            "classes": {테이블명: {개체 유형 정의}},
            "properties": {테이블명: {컬럼: 속성 정의}},
            "relations": {관계명: 관계 구조},
            "rules": {규칙명: 규칙 정의}
        }
        """
        return {
            # [1] 클래스 매핑: 테이블 -> 개체 유형
            # DB의 각 테이블을 의미론적 개체 유형으로 정의합니다
            "classes": {
                "products": {
                    "name": "Product",
                    "description": "판매되는 상품",
                    "primary_key": "id"
                },
                "categories": {
                    "name": "Category",
                    "description": "상품 분류",
                    "primary_key": "id"
                },
                "orders": {
                    "name": "Order",
                    "description": "고객 주문",
                    "primary_key": "id"
                },
                "reviews": {
                    "name": "Review",
                    "description": "상품 리뷰 및 평가",
                    "primary_key": "id"
                },
                "order_items": {
                    "name": "OrderItem",
                    "description": "주문에 포함된 상품 항목",
                    "primary_key": "id"
                },
                "social_links": {
                    "name": "SocialLink",
                    "description": "상품 소셜 미디어 링크",
                    "primary_key": "id"
                },
                "product_attributes": {
                    "name": "ProductAttribute",
                    "description": "상품의 속성값 (색상, 크기 등)",
                    "primary_key": "id"
                }
            },

            # [2] 속성 매핑: 컬럼 -> 의미 있는 속성명
            # DB 컬럼을 RDF 스타일의 의미론적 속성으로 변환합니다
            "properties": {
                "products": {
                    "id": {
                        "semantic_name": "id",
                        "type": "Identifier",
                        "description": "상품의 고유 식별자"
                    },
                    "name": {
                        "semantic_name": "hasName",
                        "type": "String",
                        "description": "상품명"
                    },
                    "price": {
                        "semantic_name": "hasPrice",
                        "type": "Numeric",
                        "unit": "KRW",
                        "description": "상품 가격"
                    },
                    "description": {
                        "semantic_name": "hasDescription",
                        "type": "Text",
                        "description": "상품 설명"
                    },
                    "image_url": {
                        "semantic_name": "hasImage",
                        "type": "URL",
                        "description": "상품 이미지 URL"
                    },
                    "created_at": {
                        "semantic_name": "createdAt",
                        "type": "DateTime",
                        "description": "생성 시간"
                    },
                    "updated_at": {
                        "semantic_name": "updatedAt",
                        "type": "DateTime",
                        "description": "마지막 수정 시간"
                    }
                },
                "categories": {
                    "id": {
                        "semantic_name": "id",
                        "type": "Identifier",
                        "description": "카테고리의 고유 식별자"
                    },
                    "name": {
                        "semantic_name": "hasName",
                        "type": "String",
                        "description": "카테고리명"
                    },
                    "description": {
                        "semantic_name": "hasDescription",
                        "type": "Text",
                        "description": "카테고리 설명"
                    }
                },
                "orders": {
                    "id": {
                        "semantic_name": "id",
                        "type": "Identifier",
                        "description": "주문의 고유 식별자"
                    },
                    "order_date": {
                        "semantic_name": "orderDate",
                        "type": "DateTime",
                        "description": "주문 날짜"
                    },
                    "total_price": {
                        "semantic_name": "hasTotalPrice",
                        "type": "Numeric",
                        "unit": "KRW",
                        "description": "주문 총액"
                    },
                    "status": {
                        "semantic_name": "hasStatus",
                        "type": "String",
                        "description": "주문 상태"
                    }
                },
                "reviews": {
                    "id": {
                        "semantic_name": "id",
                        "type": "Identifier"
                    },
                    "rating": {
                        "semantic_name": "hasRating",
                        "type": "Integer",
                        "range": "1-5",
                        "description": "평점 (1~5)"
                    },
                    "comment": {
                        "semantic_name": "hasComment",
                        "type": "Text",
                        "description": "리뷰 코멘트"
                    }
                },
                "product_attributes": {
                    "attribute_name": {
                        "semantic_name": "propertyType",
                        "type": "String",
                        "description": "속성 유형 (색상, 사이즈 등)"
                    },
                    "attribute_value": {
                        "semantic_name": "propertyValue",
                        "type": "String",
                        "description": "속성값"
                    }
                },
                "social_links": {
                    "platform": {
                        "semantic_name": "platform",
                        "type": "String",
                        "description": "소셜 미디어 플랫폼명"
                    },
                    "url": {
                        "semantic_name": "url",
                        "type": "URL",
                        "description": "소셜 미디어 링크 URL"
                    }
                }
            },

            # [3] 관계 매핑: 외래키/연결 테이블 -> 개체 간 관계
            # 개체 간의 관계를 명시적으로 정의합니다
            "relations": {
                "product_categories": {
                    "source_table": "products",
                    "source_key": "product_id",
                    "target_table": "categories",
                    "target_key": "category_id",
                    "relation_name": "belongsToCategory",
                    "description": "상품이 카테고리에 속함"
                },
                "product_attributes": {
                    "source_table": "products",
                    "source_key": "product_id",
                    "relation_name": "hasAttribute",
                    "description": "상품이 속성을 가짐"
                },
                "product_reviews": {
                    "source_table": "products",
                    "source_key": "product_id",
                    "relation_name": "hasReview",
                    "description": "상품이 리뷰를 가짐"
                },
                "product_social_links": {
                    "source_table": "products",
                    "source_key": "product_id",
                    "relation_name": "hasSocialLink",
                    "description": "상품이 소셜 링크를 가짐"
                },
                "order_items": {
                    "source_table": "orders",
                    "source_key": "order_id",
                    "relation_name": "containsOrderItem",
                    "description": "주문이 주문항목을 포함함"
                }
            },

            # [4] 규칙 매핑: 데이터 제약 -> 의미 규칙
            # 의미론적 제약 조건 및 검증 규칙을 정의합니다
            "rules": {
                "price_positive": {
                    "description": "상품 가격은 양수",
                    "constraint": "price > 0",
                    "severity": "error"
                },
                "name_required": {
                    "description": "상품명은 필수",
                    "constraint": "name IS NOT NULL",
                    "severity": "error"
                },
                "rating_range": {
                    "description": "평점은 1~5 범위",
                    "constraint": "rating >= 1 AND rating <= 5",
                    "severity": "error"
                },
                "quantity_positive": {
                    "description": "주문 수량은 양수",
                    "constraint": "quantity > 0",
                    "severity": "error"
                }
            }
        }

    def extract_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Step 2: 단일 상품 데이터 추출 (Extraction)

        하나의 상품 행(row)을 의미 구조로 변환합니다.
        이 메서드는 기본 상품 정보만 추출하며, 관계는 포함하지 않습니다.

        Args:
            product_id (int): 추출할 상품의 ID

        Returns:
            Optional[Dict[str, Any]]: 의미 구조로 변환된 상품 데이터,
                                      존재하지 않으면 None

        반환 구조:
        {
            "type": "Product",
            "id": 1,
            "hasName": "상품명",
            "hasPrice": {"value": 1000, "currency": "KRW"},
            "hasDescription": "설명",
            "hasImage": "URL",
            "createdAt": "2024-01-01T00:00:00",
            "updatedAt": "2024-01-01T00:00:00"
        }
        """
        # DB에서 해당 ID의 상품 정보 조회
        # 읽기만 수행하며, 데이터 수정은 하지 않습니다
        self.cursor.execute("""
            SELECT id, name, price, description, image_url, created_at, updated_at
            FROM products
            WHERE id = ?
        """, (product_id,))

        # 쿼리 결과 가져오기
        product_row = self.cursor.fetchone()

        # 상품이 존재하지 않으면 None 반환
        if not product_row:
            return None

        # 매핑 규칙을 적용하여 의미 있는 구조로 변환
        # 각 DB 컬럼을 의미론적 속성명으로 변환합니다
        semantic_product = {
            "type": "Product",  # 개체 유형 명시
            "id": product_row["id"],
            "hasName": product_row["name"],
            "hasPrice": {
                # 가격을 단위 정보와 함께 구조화
                "value": float(product_row["price"]),
                "currency": "KRW"
            },
            "hasDescription": product_row["description"],
            "hasImage": product_row["image_url"],
            "createdAt": product_row["created_at"],
            "updatedAt": product_row["updated_at"]
        }

        return semantic_product

    def extract_product_with_relations(self, product_id: int) -> Optional[Dict[str, Any]]:
        """
        Step 3: 관계를 포함한 완전한 상품 정보 추출 (Relations)

        상품의 모든 관계(카테고리, 속성, 리뷰, 소셜링크)를 포함하여 추출합니다.
        이는 상품의 완전한 의미 구조를 제공합니다.

        Args:
            product_id (int): 추출할 상품의 ID

        Returns:
            Optional[Dict[str, Any]]: 관계를 포함한 완전한 의미 구조

        반환 구조:
        {
            ...기본 상품 정보...,
            "belongsToCategory": [...],
            "hasAttribute": [...],
            "hasReview": [...],
            "hasSocialLink": [...]
        }
        """
        # 기본 상품 정보 추출
        product = self.extract_product(product_id)
        if not product:
            return None

        # [관계 1] 카테고리 추출
        # 상품이 속한 모든 카테고리를 찾습니다
        self.cursor.execute("""
            SELECT c.id, c.name, c.description
            FROM categories c
            JOIN product_categories pc ON c.id = pc.category_id
            WHERE pc.product_id = ?
        """, (product_id,))

        # 카테고리 정보를 의미 구조로 변환
        categories = [
            {
                "type": "Category",
                "id": row["id"],
                "hasName": row["name"],
                "hasDescription": row["description"]
            }
            for row in self.cursor.fetchall()
        ]
        product["belongsToCategory"] = categories

        # [관계 2] 속성 추출
        # 상품의 모든 속성(색상, 사이즈 등)을 찾습니다
        self.cursor.execute("""
            SELECT attribute_name, attribute_value, sort_order
            FROM product_attributes
            WHERE product_id = ?
            ORDER BY sort_order, id
        """, (product_id,))

        # 속성 정보를 의미 구조로 변환
        attributes = [
            {
                "propertyType": row["attribute_name"],
                "propertyValue": row["attribute_value"]
            }
            for row in self.cursor.fetchall()
        ]
        product["hasAttribute"] = attributes

        # [관계 3] 리뷰 추출
        # 상품에 달린 모든 리뷰를 찾습니다
        self.cursor.execute("""
            SELECT id, rating, comment, created_at
            FROM reviews
            WHERE product_id = ?
            ORDER BY created_at DESC
        """, (product_id,))

        # 리뷰 정보를 의미 구조로 변환
        reviews = [
            {
                "type": "Review",
                "id": row["id"],
                "hasRating": row["rating"],
                "hasComment": row["comment"],
                "createdAt": row["created_at"]
            }
            for row in self.cursor.fetchall()
        ]
        product["hasReview"] = reviews

        # [관계 4] 소셜 링크 추출
        # 상품과 관련된 모든 소셜 미디어 링크를 찾습니다
        self.cursor.execute("""
            SELECT platform, url, created_at
            FROM social_links
            WHERE product_id = ?
            ORDER BY created_at
        """, (product_id,))

        # 소셜 링크를 의미 구조로 변환
        social_links = [
            {
                "type": "SocialLink",
                "platform": row["platform"],
                "url": row["url"]
            }
            for row in self.cursor.fetchall()
        ]
        product["hasSocialLink"] = social_links

        return product

    def extract_all_products(self, with_relations: bool = False) -> List[Dict[str, Any]]:
        """
        모든 상품 데이터 일괄 추출

        데이터베이스의 모든 상품을 추출합니다.

        Args:
            with_relations (bool): True면 관계 포함, False면 기본 정보만

        Returns:
            List[Dict[str, Any]]: 추출된 모든 상품의 목록
        """
        # 모든 상품 ID 조회
        self.cursor.execute("SELECT id FROM products ORDER BY id")
        product_ids = [row["id"] for row in self.cursor.fetchall()]

        # 각 상품 추출 (with_relations 옵션에 따라)
        if with_relations:
            products = [
                self.extract_product_with_relations(pid)
                for pid in product_ids
            ]
        else:
            products = [
                self.extract_product(pid)
                for pid in product_ids
            ]

        # None 값 필터링 (존재하지 않는 상품 제외)
        return [p for p in products if p is not None]

    def extract_category_with_products(self, category_id: int) -> Optional[Dict[str, Any]]:
        """
        카테고리와 해당하는 모든 상품 추출

        특정 카테고리에 속한 모든 상품을 포함하여 카테고리를 추출합니다.

        Args:
            category_id (int): 추출할 카테고리의 ID

        Returns:
            Optional[Dict[str, Any]]: 상품을 포함한 카테고리 정보
        """
        # 카테고리 기본 정보 조회
        self.cursor.execute("""
            SELECT id, name, description
            FROM categories
            WHERE id = ?
        """, (category_id,))

        category_row = self.cursor.fetchone()
        if not category_row:
            return None

        # 카테고리 기본 구조 생성
        category = {
            "type": "Category",
            "id": category_row["id"],
            "hasName": category_row["name"],
            "hasDescription": category_row["description"]
        }

        # 해당 카테고리에 속한 모든 상품 조회
        self.cursor.execute("""
            SELECT p.id, p.name, p.price, p.image_url
            FROM products p
            JOIN product_categories pc ON p.id = pc.product_id
            WHERE pc.category_id = ?
            ORDER BY p.id
        """, (category_id,))

        # 상품 정보를 의미 구조로 변환
        products = [
            {
                "type": "Product",
                "id": row["id"],
                "hasName": row["name"],
                "hasPrice": {
                    "value": float(row["price"]),
                    "currency": "KRW"
                },
                "hasImage": row["image_url"]
            }
            for row in self.cursor.fetchall()
        ]

        category["hasProduct"] = products
        return category

    def extract_order_with_items(self, order_id: int) -> Optional[Dict[str, Any]]:
        """
        주문과 주문항목 추출

        특정 주문의 상세 정보와 포함된 모든 상품을 추출합니다.

        Args:
            order_id (int): 추출할 주문의 ID

        Returns:
            Optional[Dict[str, Any]]: 주문항목을 포함한 주문 정보
        """
        # 주문 기본 정보 조회
        self.cursor.execute("""
            SELECT id, order_date, total_price, status, created_at, updated_at
            FROM orders
            WHERE id = ?
        """, (order_id,))

        order_row = self.cursor.fetchone()
        if not order_row:
            return None

        # 주문 기본 구조 생성
        order = {
            "type": "Order",
            "id": order_row["id"],
            "orderDate": order_row["order_date"],
            "hasTotalPrice": {
                "value": float(order_row["total_price"]),
                "currency": "KRW"
            },
            "hasStatus": order_row["status"],
            "createdAt": order_row["created_at"],
            "updatedAt": order_row["updated_at"]
        }

        # 주문에 포함된 모든 항목 조회
        self.cursor.execute("""
            SELECT oi.id, oi.product_id, oi.quantity, oi.price,
                   p.name, p.image_url
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        """, (order_id,))

        # 주문항목을 의미 구조로 변환
        order_items = [
            {
                "type": "OrderItem",
                "id": row["id"],
                "containsProduct": {
                    "type": "Product",
                    "id": row["product_id"],
                    "hasName": row["name"],
                    "hasImage": row["image_url"]
                },
                "quantity": row["quantity"],
                "price": {
                    "value": float(row["price"]),
                    "currency": "KRW"
                }
            }
            for row in self.cursor.fetchall()
        ]

        order["containsOrderItem"] = order_items
        return order

    def extract_category_statistics(self) -> Dict[str, Any]:
        """
        카테고리별 통계 정보 추출

        각 카테고리의 상품 개수, 평균 가격 등의 통계를 추출합니다.

        Returns:
            Dict[str, Any]: 카테고리별 통계 정보
        """
        # 카테고리별 통계 쿼리
        self.cursor.execute("""
            SELECT
                c.id,
                c.name,
                COUNT(pc.product_id) as product_count,
                AVG(p.price) as avg_price,
                MIN(p.price) as min_price,
                MAX(p.price) as max_price
            FROM categories c
            LEFT JOIN product_categories pc ON c.id = pc.category_id
            LEFT JOIN products p ON pc.product_id = p.id
            GROUP BY c.id, c.name
            ORDER BY c.id
        """)

        # 통계를 의미 구조로 변환
        stats = [
            {
                "type": "CategoryStatistics",
                "category": {
                    "id": row["id"],
                    "hasName": row["name"]
                },
                "productCount": row["product_count"],
                "averagePrice": {
                    "value": round(float(row["avg_price"]), 2) if row["avg_price"] else 0,
                    "currency": "KRW"
                },
                "minimumPrice": {
                    "value": float(row["min_price"]) if row["min_price"] else 0,
                    "currency": "KRW"
                },
                "maximumPrice": {
                    "value": float(row["max_price"]) if row["max_price"] else 0,
                    "currency": "KRW"
                }
            }
            for row in self.cursor.fetchall()
        ]

        return {
            "type": "StatisticsCollection",
            "categoryStatistics": stats,
            "generatedAt": datetime.now().isoformat()
        }

    def validate_semantic_data(self, semantic_data: Dict[str, Any]) -> bool:
        """
        Step 4: 의미 데이터 검증 (Validation)

        추출한 의미 데이터가 정의된 규칙을 만족하는지 검증합니다.

        Args:
            semantic_data (Dict[str, Any]): 검증할 의미 구조

        Returns:
            bool: 검증 성공 여부 (True: 유효, False: 무효)
        """
        # 데이터가 None이거나 비어있는 경우 검증 실패
        if not semantic_data:
            print("[검증 실패] 데이터가 비어있습니다")
            return False

        # 필수 필드 확인: type (개체 유형)
        if "type" not in semantic_data:
            print("[검증 실패] 개체 유형(type)이 없습니다")
            return False

        entity_type = semantic_data["type"]

        # 상품(Product) 검증
        if entity_type == "Product":
            # 필수 필드: hasName
            if "hasName" not in semantic_data or not semantic_data["hasName"]:
                print("[검증 실패] 상품명(hasName)이 필수입니다")
                return False

            # 가격 검증
            if "hasPrice" in semantic_data:
                price_value = semantic_data["hasPrice"]["value"]
                if price_value <= 0:
                    print(f"[검증 실패] 가격은 양수여야 합니다 (입력값: {price_value})")
                    return False

        # 리뷰(Review) 검증
        elif entity_type == "Review":
            # 필수 필드: hasRating
            if "hasRating" not in semantic_data:
                print("[검증 실패] 평점(hasRating)이 필수입니다")
                return False

            rating = semantic_data["hasRating"]
            if not (1 <= rating <= 5):
                print(f"[검증 실패] 평점은 1~5 범위여야 합니다 (입력값: {rating})")
                return False

        # 주문항목(OrderItem) 검증
        elif entity_type == "OrderItem":
            # 필수 필드: quantity
            if "quantity" not in semantic_data:
                print("[검증 실패] 수량(quantity)이 필수입니다")
                return False

            quantity = semantic_data["quantity"]
            if quantity <= 0:
                print(f"[검증 실패] 수량은 양수여야 합니다 (입력값: {quantity})")
                return False

        # 모든 검증 통과
        return True

    def represent_as_json(self, semantic_data: Dict[str, Any], indent: int = 2) -> str:
        """
        Step 5: 의미 구조를 JSON으로 표현 (Representation)

        의미 구조를 JSON 문자열로 변환합니다.
        이를 통해 다른 시스템과 호환 가능한 형식으로 데이터를 표현합니다.

        Args:
            semantic_data (Dict[str, Any]): 의미 구조
            indent (int): JSON 들여쓰기 크기 (기본값: 2)

        Returns:
            str: JSON 형식의 문자열
        """
        # ensure_ascii=False: 한글 등 비ASCII 문자 그대로 표현
        # indent: 정렬된 JSON (None이면 한 줄로 표현)
        return json.dumps(
            semantic_data,
            ensure_ascii=False,
            indent=indent,
            default=str  # datetime 등의 객체를 문자열로 변환
        )

    def get_schema_info(self) -> Dict[str, Any]:
        """
        데이터베이스 스키마 정보 반환

        데이터베이스의 테이블 구조와 정의된 매핑 규칙을 표시합니다.

        Returns:
            Dict[str, Any]: 스키마 및 매핑 정보
        """
        return {
            "type": "SchemaInfo",
            "classes": self.semantic_mappings["classes"],
            "relations": self.semantic_mappings["relations"],
            "rules": self.semantic_mappings["rules"]
        }

    def close(self):
        """
        데이터베이스 연결 종료

        사용을 마친 후 반드시 호출하여 리소스를 해제합니다.
        """
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager 지원: with 문 사용 가능"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: 자동으로 DB 연결 종료"""
        self.close()
        return False


# ============================================================================
# 사용 예제
# ============================================================================

def main():
    """
    Semantic Layer 사용 예제

    학습 과정:
    1. Semantic Layer 객체 생성 (DB 연결)
    2. 매핑 규칙 확인
    3. 단일 상품 추출 (Step 2)
    4. 관계를 포함한 추출 (Step 3)
    5. 검증 (Step 4)
    6. JSON으로 표현 (Step 5)
    7. 추가 기능 활용
    """
    # 데이터베이스 경로 설정
    # 아래 경로를 실제 tiny_mall.db 파일 위치로 변경하세요
    db_path = "../tiny-mall/db/tiny_mall.db"

    # 상대 경로가 작동하지 않으면 절대 경로 사용:
    # db_path = "/path/to/tiny_mall.db"

    print("=" * 80)
    print("Tiny Mall Semantic Layer 예제")
    print("=" * 80)

    # Context manager를 사용하여 자동으로 DB 연결 종료
    with SemanticLayer(db_path) as semantic_layer:

        # [Step 1] 매핑 규칙 확인
        print("\n[Step 1] 의미 매핑 규칙 확인")
        print("-" * 80)
        print("클래스 매핑 (테이블 -> 개체):")
        for table, mapping in semantic_layer.semantic_mappings["classes"].items():
            print(f"  {table:20} -> {mapping['name']:20} ({mapping['description']})")

        print("\n관계 매핑 (FK/연결테이블 -> 관계):")
        for relation_name, relation_info in semantic_layer.semantic_mappings["relations"].items():
            print(f"  {relation_name:25} : {relation_info['description']}")

        # [Step 2] 단일 상품 추출
        print("\n\n[Step 2] 단일 상품 기본 정보 추출")
        print("-" * 80)
        product_id = 1
        product = semantic_layer.extract_product(product_id)
        if product:
            print(f"상품 ID {product_id}:")
            print(semantic_layer.represent_as_json(product))
        else:
            print(f"상품 ID {product_id}를 찾을 수 없습니다")

        # [Step 3] 관계를 포함한 완전한 추출
        print("\n\n[Step 3] 관계를 포함한 완전한 상품 정보 추출")
        print("-" * 80)
        product_with_relations = semantic_layer.extract_product_with_relations(product_id)
        if product_with_relations:
            print(f"상품 ID {product_id} (모든 관계 포함):")
            print(semantic_layer.represent_as_json(product_with_relations))

        # [Step 4] 검증
        print("\n\n[Step 4] 추출된 의미 데이터 검증")
        print("-" * 80)
        is_valid = semantic_layer.validate_semantic_data(product_with_relations)
        if is_valid:
            print("검증 결과: 통과 (모든 규칙을 만족합니다)")
        else:
            print("검증 결과: 실패 (규칙을 위반합니다)")

        # [추가 기능] 카테고리별 통계
        print("\n\n[추가 기능] 카테고리별 통계")
        print("-" * 80)
        stats = semantic_layer.extract_category_statistics()
        print(semantic_layer.represent_as_json(stats))

        # [추가 기능] 모든 상품 (관계 포함)
        print("\n\n[추가 기능] 모든 상품 목록 (기본 정보만)")
        print("-" * 80)
        all_products = semantic_layer.extract_all_products(with_relations=False)
        print(f"총 {len(all_products)}개의 상품이 있습니다:")
        for prod in all_products[:3]:  # 처음 3개만 표시
            print(f"  - {prod['hasName']} (ID: {prod['id']}, 가격: {prod['hasPrice']['value']:,} {prod['hasPrice']['currency']})")

        # [추가 기능] 주문 정보 조회
        print("\n\n[추가 기능] 주문 정보 추출 (첫 번째 주문)")
        print("-" * 80)
        order = semantic_layer.extract_order_with_items(order_id=1)
        if order:
            print(semantic_layer.represent_as_json(order))
        else:
            print("주문 정보를 찾을 수 없습니다")


if __name__ == "__main__":
    main()
