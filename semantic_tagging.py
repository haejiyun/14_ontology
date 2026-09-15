import sqlite3
import pandas as pd
from rdflib import Graph, Literal, Namespace, RDF, OWL, RDFS, URIRef
from rdflib.namespace import XSD
from decimal import Decimal


conn=sqlite3.connect("db/tiny_mall.db")
conn.row_factory = sqlite3.Row
MALL = Namespace("https://fastcampus.co.kr/data_online_ontology2/")



######Property Mapping
PRODUCT_PROP_MAP = {
    "name": (MALL["hasName"], None),           
    "price": (MALL["hasPrice"], XSD.decimal),
    "description": (MALL["hasDescription"], None),
    "image_url": (MALL["hasImage"], XSD.anyURI),
}

# EAV 속성 매핑 (product_attributes.attribute_name → TBox 속성)
ATTR_MAP = {
    # 한국어
    "CPU": "hasCPU",
    "GPU": "hasGPU",
    "RAM": "hasRAM",
    "화면크기": "hasScreenSize",
    "프로세서": "hasCPU",
    "메모리": "hasRAM",
    "저장공간": "hasStorage",
    "해상도": "hasResolution",
    "무게": "hasWeight",
    "배터리": "hasBattery",
    "OS": "hasOS",
    "그래픽카드": "hasGPU",
    "포트": "hasPort",
    # 중국어
    "屏幕尺寸": "hasScreenSize",
    "存储空间": "hasStorage",
    "操作系统": "hasOS",
    "处理器架构": "hasProcessorArchitecture",
    "神经引擎": "hasNeuralEngine",
    "内存带宽": "hasMemoryBandwidth",
    "功耗": "hasPowerConsumption",
    # 영어 변형
    "Battery": "hasBattery",
    "Battery Life": "hasBattery",
    "BatteryLife": "hasBattery",
    "Screen Size": "hasScreenSize",
    "DisplaySize": "hasScreenSize",
    "Display Size": "hasScreenSize",
    "Storage": "hasStorage",
    "SSD": "hasStorage",
    "Weight": "hasWeight",
    "Resolution": "hasResolution",
    "Display Resolution": "hasResolution",
    "Memory": "hasRAM",
    "Graphics": "hasGPU",
    "Operating System": "hasOS",
    "Operating_System": "hasOS",
    "Processor": "hasCPU",
    "Display": "hasScreenSize",
    "Color": "hasColor",
    "Ports": "hasPort",
}

# 카테고리 → Product 서브클래스 매핑
CATEGORY_CLASS_MAP = {
    "노트북": MALL["Electronics"],
    "전자제품": MALL["Electronics"],
    "데스크탑": MALL["Electronics"],
    "태블릿": MALL["Electronics"],
}

# 비정상 가격 임계값 (원 단위)
SUSPICIOUS_PRICE_THRESHOLD = 1000



######RDF Conversion
g=Graph()
g.parse('db/tbox.ttl', format='turtle')
g.bind('mall', MALL)

#Category
categories = conn.execute("SELECT id, name, description FROM categories").fetchall()
count = 0
for cat in categories:
    cat_uri=MALL[f"category/{cat['id']}"]
    g.add((cat_uri, RDF.type, MALL["Category"]))
    g.add((cat_uri, MALL["hasCategoryName"], Literal(cat["name"])))
    if cat["description"]:
        g.add((cat_uri, MALL["hasDescription"], Literal(cat["description"])))
    count += 1

#Product
result = {"tagged": 0, "skipped": [], "suspicious": []}
for row in conn.execute(
    "SELECT p.id, p.name, p.price, p.description, p.image_url,c.id AS cat_id, c.name AS cat_name\
    FROM products p\
    JOIN product_categories pc ON p.id = pc.product_id\
    JOIN categories c ON pc.category_id = c.id"
    ).fetchall():
    product_id = row["id"]
    product_uri = MALL[f"product/{product_id}"]
    cat_name = row["cat_name"]
    
    if cat_name in CATEGORY_CLASS_MAP:
        g.add((product_uri, RDF.type, CATEGORY_CLASS_MAP[cat_name]))
    else:
        g.add((product_uri, RDF.type, MALL["Product"]))

    for col, (prop, dtype) in PRODUCT_PROP_MAP.items():
        val = row[col]
        if val is None:
            continue
        if dtype == XSD.decimal:
            g.add((product_uri, prop, Literal(Decimal(str(val)), datatype=XSD.decimal)))
        elif dtype:
            g.add((product_uri, prop, Literal(val, datatype=dtype)))
        else:
            g.add((product_uri, prop, Literal(str(val))))

    cat_uri = MALL[f"category/{row['cat_id']}"]
    g.add((product_uri, MALL["belongsToCategory"], cat_uri))

    if row["price"] < SUSPICIOUS_PRICE_THRESHOLD:
        g.add((product_uri, RDFS.comment,
                Literal(f"의심 가격: {row['price']}원 (임계값 {SUSPICIOUS_PRICE_THRESHOLD}원 미만)", lang="ko")))
        result["suspicious"].append(
            (product_id, row["name"], row["price"])
        )
    result["tagged"] += 1

#Reviews
review_count = 0
for review in conn.execute("SELECT id, product_id, rating, comment FROM reviews").fetchall():
    review_uri = MALL[f"review/{review['id']}"]
    product_uri = MALL[f"product/{review['product_id']}"]

    g.add((review_uri, RDF.type, MALL["Review"]))
    g.add((review_uri, MALL["reviewOf"], product_uri))
    g.add((
        review_uri,
        MALL["hasRating"],
        Literal(review["rating"], datatype=XSD.integer),
    ))
    if review["comment"]:
        g.add((review_uri, MALL["hasComment"], Literal(review["comment"])))
    review_count += 1

#Attributes
attribute_count = 0
unmapped = set()
for attr in conn.execute(
    """
    SELECT product_id, attribute_name, attribute_value
    FROM product_attributes
    ORDER BY product_id, sort_order
    """
    ).fetchall():
    attr_name = attr["attribute_name"]
    if attr_name not in ATTR_MAP:
        unmapped.add(attr_name)
        continue
    product_uri = MALL[f"product/{attr['product_id']}"]
    prop_name = ATTR_MAP[attr_name]
    g.add((product_uri, MALL[prop_name], Literal(attr["attribute_value"])))
    attribute_count += 1




g.serialize("db/abox.ttl", format="turtle")