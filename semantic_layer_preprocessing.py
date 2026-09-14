import sqlite3
import pandas as pd


######DB Connexion
conn=sqlite3.connect("db/tiny_mall.db")
cursor=conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables=cursor.fetchall()
tables #products, categories, orders, product_categories, reviews, social_links, order_items, product_attributes

cursor.execute("SELECT * FROM products")
cursor.fetchall()

cursor.execute("SELECT count(*) FROM products").fetchall()


######Data Check
pd.set_option('display.max_columns',None)

product = pd.read_sql_query("SELECT * FROM products", conn)
product.head()

product_attributes = pd.read_sql_query("SELECT * FROM product_attributes",conn)
product_attributes.info()
product_attributes.head()

categories = pd.read_sql_query("SELECT * FROM categories", conn)
categories.info()
categories.head()

orders = pd.read_sql_query("SELECT * FROM orders", conn)
orders.info()

order_items = pd.read_sql_query("SELECT * FROM order_items", conn)
order_items.info()

product_categories = pd.read_sql_query("SELECT * FROM product_categories", conn)
product_categories.info()

reviews = pd.read_sql_query("SELECT * FROM reviews", conn)
reviews.info()

social_links = pd.read_sql_query("SELECT * FROM social_links", conn)
social_links.info()



######Preprocessing
pd.set_option('display.max_rows',None)

COLOR_KEYWORDS = [
    "베이지", "블랙", "화이트", "실버", "그라파이트",
    "그레이", "검정", "회색", "흰색", "검은색",
    "블루", "핑크", "그린", "골드", "로즈",
    "미스틱 실버", "미스틱 블랙", "스타라이트",
]


#Mapping Rules
"""
Returns:
    Dict[str, Any]: 의미 매핑 규칙 사전
구조:
{
    "classes": {테이블명: {개체 유형 정의}},
    "properties": {테이블명: {컬럼: 속성 정의}} --> ex. hasName/ hasPrice,
    "relations": {관계명: 관계 구조} --> ex. belongsToCategory,
    "rules": {규칙명: 규칙 정의}
}
"""
semantic_mappings = {
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


#self.db_path = db_path
#self.conn = sqlite3.connect(db_path)
#self.conn.row_factory = sqlite3.Row
#self.cursor = self.conn.cursor()
#self.semantic_mappings = self._define_mappings()
#Extract Product Property
"""
Args:
    product_id (int): 추출할 상품의 ID
Returns:
    Optional[Dict[str, Any]]: 의미 구조로 변환된 상품 데이터, 존재하지 않으면 None
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
semantic_products=[]
for prod in product.itertuples(index=False):
    semantic_product={
        "type":"Product",
        "id":prod.id,
        "hasName":prod.name,
        "hasPrice":{
            "value":float(prod.price),
            "currency":"KRW"
        },
        "hasDescription":prod.description,
        "hasImage":prod.image_url,
        "createdAt":prod.created_at,
        "updatedAt":prod.updated_at
    }
    semantic_products.append(semantic_product)

