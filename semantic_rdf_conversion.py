import sqlite3
import pandas as pd
import re
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

# 추론 임계값 (도메인 전문가 조정 가능)
PORTABLE_WEIGHT_KG = 2.0       # 2kg 미만 → 휴대 가능
ULTRALIGHT_KG = 1.5            # 1.5kg 미만 → 초경량
LONG_BATTERY_WH = 60           # 60Wh 이상 → 장시간 사용
PREMIUM_PRICE = 2_000_000      # 200만원 이상 → 프리미엄
MIDRANGE_PRICE = 800_000       # 80만원 이상 → 중급
HIGH_PERF_RAM_GB = 32          # 32GB 이상 → 고성능
LARGE_SCREEN_INCH = 15         # 15인치 이상 → 대화면
SMALL_SCREEN_INCH = 13         # 13인치 이하 → 소형

# 속성 키 정규화 (KEY_ALIAS)
KEY_ALIAS: dict[str, str] = {
    # 무게 → weight
    "무게": "weight", "Weight": "weight", "重量": "weight",
    # 메모리 → ram
    "메모리": "ram", "RAM": "ram", "Memory": "ram", "내존대역폭": "ram",
    # 배터리 → battery
    "배터리": "battery", "Battery": "battery", "Battery Life": "battery",
    "BatteryLife": "battery", "Battery_Life": "battery", "Battery_Time": "battery",
    "배터리 사용 시간": "battery", "배터리 시간": "battery",
    "배터리수명": "battery", "배터리시간": "battery", "배터리용량": "battery",
    "电池容量": "battery",
    # 화면 → screen
    "화면크기": "screen", "화면 크기": "screen", "Screen Size": "screen",
    "DisplaySize": "screen", "Display_Size": "screen", "Display Size": "screen",
    "Display": "screen", "屏幕尺寸": "screen",
    # GPU → gpu
    "GPU": "gpu", "그래픽카드": "gpu", "Graphics": "gpu",
    # CPU → cpu
    "CPU": "cpu", "프로세서": "cpu", "Processor": "cpu",
    "处理器类型": "cpu", "处理器架构": "cpu",
    # 저장공간 → storage
    "저장공간": "storage", "Storage": "storage", "SSD": "storage", "存储空间": "storage",
    # 해상도 → resolution
    "해상도": "resolution", "Resolution": "resolution", "Display Resolution": "resolution",
    "디스플레이해상도": "resolution", "화면해상도": "resolution",
    "屏幕分辨率": "resolution", "分辨率": "resolution",
    # OS → os
    "OS": "os", "Operating_System": "os", "Operating System": "os", "操作系统": "os",
    # 색상 → color
    "색상": "color", "Color": "color", "颜色": "color",
    # 포트 → port
    "포트": "port", "Ports": "port", "Connector": "port", "연결방식": "port",
}

# EAV 속성명 → TBox 데이터 속성 매핑 (직접 매핑용)
SPEC_TO_RDF: dict[str, str] = {
    "CPU": "hasCPU", "프로세서": "hasCPU", "Processor": "hasCPU",
    "处理器类型": "hasCPU", "处理器架构": "hasProcessorArchitecture",
    "GPU": "hasGPU", "그래픽카드": "hasGPU", "Graphics": "hasGPU",
    "RAM": "hasRAM", "메모리": "hasRAM", "Memory": "hasRAM",
    "화면크기": "hasScreenSize", "화면 크기": "hasScreenSize",
    "Screen Size": "hasScreenSize", "DisplaySize": "hasScreenSize",
    "Display_Size": "hasScreenSize", "Display Size": "hasScreenSize",
    "Display": "hasScreenSize", "屏幕尺寸": "hasScreenSize",
    "저장공간": "hasStorage", "Storage": "hasStorage", "SSD": "hasStorage",
    "存储空间": "hasStorage",
    "해상도": "hasResolution", "Resolution": "hasResolution",
    "Display Resolution": "hasResolution", "디스플레이해상도": "hasResolution",
    "화면해상도": "hasResolution", "屏幕分辨率": "hasResolution", "分辨率": "hasResolution",
    "무게": "hasWeight", "Weight": "hasWeight", "重量": "hasWeight",
    "배터리": "hasBattery", "Battery": "hasBattery", "Battery Life": "hasBattery",
    "BatteryLife": "hasBattery", "Battery_Life": "hasBattery",
    "Battery_Time": "hasBattery",
    "배터리 사용 시간": "hasBattery", "배터리 시간": "hasBattery",
    "배터리수명": "hasBattery", "배터리시간": "hasBattery", "배터리용량": "hasBattery",
    "电池容量": "hasBattery",
    "OS": "hasOS", "Operating_System": "hasOS", "Operating System": "hasOS",
    "操作系统": "hasOS",
    "색상": "hasColor", "Color": "hasColor", "颜色": "hasColor",
    "포트": "hasPort", "Ports": "hasPort", "Connector": "hasPort",
    "연결방식": "hasPort",
    "神经引擎": "hasNeuralEngine",
    "内存带宽": "hasMemoryBandwidth",
    "功耗": "hasPowerConsumption",
}



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



#Product with context
result = {
    "tagged": 0,
    "skipped": [],
    "suspicious": [],
    "spec_triples": 0,
    "context_stats": {
        "with_purpose": 0,
        "with_situation": 0,
        "with_price_range": 0,
        "with_portability": 0,
        "incomplete": 0,
    },
    "unmapped_attrs": set(),
}

attr_map: dict[int, dict[str, str]] = {}
for row in conn.execute(
    """
    SELECT product_id, attribute_name, attribute_value
    FROM product_attributes
    ORDER BY product_id, sort_order
    """
    ).fetchall():
    pid = row["product_id"]
    if pid not in attr_map:
        attr_map[pid] = {}
    attr_map[pid][row["attribute_name"]] = row["attribute_value"]

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

    raw_attrs = attr_map.get(product_id, {})
    spec_count = 0
    for key, val in raw_attrs.items():
        prop = SPEC_TO_RDF.get(key)
        if prop:
            g.add((product_uri, MALL[prop], Literal(val)))
            spec_count += 1
    result["spec_triples"] += spec_count

    for key in raw_attrs:
        if key not in SPEC_TO_RDF:
            result["unmapped_attrs"].add(key)

    specs: dict = {}
    for key, val in raw_attrs.items():
        std_key = KEY_ALIAS.get(key)
        if not std_key:
            continue

        nums = re.findall(r"[\d.]+", val)
        try:
            nums = float(nums[0]) 
        except:
            nums = None
        
        if std_key == "weight":
            if nums is not None:
                if "lb" in val.lower():
                    nums= round(nums * 0.4536, 2)
                if nums > 10:  # g → kg 변환 (예: 1600 → 1.6)
                    nums= round(nums / 1000, 2)
            specs["weight_kg"] = nums
        elif std_key == "battery":
            specs["battery_wh"] = nums
        elif std_key == "ram":
            specs["ram_gb"] = nums
        elif std_key == "screen":
            specs["screen_inch"] = nums
        elif std_key == "gpu":
            specs["has_gpu"] = True
            specs["gpu_name"] = val
        elif std_key == "cpu":
            match = re.search(r"(\d+)\s*코어|(\d+)\s*[Cc]ore", val)
            if match:
                cpu_cores= int(match.group(1) or match.group(2))
            cpu_cores=None
            specs["cpu_cores"] = cpu_cores

    ctx = {"purposes": [], "situations": [], "price_range": None, "portability": None, "incomplete": False}
    
    # 용도 태깅
    purposes = []
    if specs.get("has_gpu"):
        gpu = specs.get("gpu_name", "")
        if "RTX" in gpu or "GeForce" in gpu:
            purposes.append("게이밍")
        purposes.append("영상편집")
        purposes.append("3D 렌더링")
    ram = specs.get("ram_gb")
    if ram and ram >= HIGH_PERF_RAM_GB:
        purposes.append("개발")
        purposes.append("데이터 분석")
        
    for p in purposes:
        g.add((product_uri, MALL["hasPurpose"], Literal(p)))
    result["purposes"] = purposes

    # 상황 태깅
    situations = []
    w = specs.get("weight_kg")
    b = specs.get("battery_wh")
    if w and w < ULTRALIGHT_KG and b and b >= LONG_BATTERY_WH:
        situations.extend(["출장", "카페", "야외"])
    elif w and w < PORTABLE_WEIGHT_KG:
        situations.extend(["사무실", "이동 업무"])
    elif w and w >= PORTABLE_WEIGHT_KG:
        situations.append("고정 데스크")
    if specs.get("has_gpu"):
        situations.append("스튜디오")

    for s in situations:
        g.add((product_uri, MALL["hasSituation"], Literal(s)))

    # 화면 크기 기반 상황 보충
    inch = specs.get("screen_inch")
    screen_uses = []
    if inch is not None:
        if inch >= LARGE_SCREEN_INCH:
            screen_uses.append("멀티태스킹")
            screen_uses.append("고정 데스크")
        elif inch <= SMALL_SCREEN_INCH:
            screen_uses.append("이동용")

    for u in screen_uses:
        g.add((product_uri, MALL["hasSituation"], Literal(u)))
    result["situations"] = situations + screen_uses

    # 가격대 분류
    price=row["price"]
    if price <= 0:
        tier=None
    if price >= PREMIUM_PRICE:
        tier="프리미엄"
    elif price >= MIDRANGE_PRICE:
        tier="중급"
    else:
        tier="보급형"

    if tier:
        g.add((product_uri, MALL["hasPriceRange"], Literal(tier)))
    result["price_range"] = tier

    # 휴대성 판단
    w = specs.get("weight_kg")
    if w:
        label = "휴대 가능" if w < PORTABLE_WEIGHT_KG else "거치형"
        g.add((product_uri, MALL["hasPortability"], Literal(label)))
        result["portability"] = label

    # 데이터 간극 마킹: 무게 또는 배터리 정보 누락 시
    if not specs.get("weight_kg") or not specs.get("battery_wh"):
        g.add((product_uri, MALL["isIncomplete"], Literal(True)))
        result["incomplete"] = True

    if ctx["purposes"]:
        result["context_stats"]["with_purpose"] += 1
    if ctx["situations"]:
        result["context_stats"]["with_situation"] += 1
    if ctx["price_range"]:
        result["context_stats"]["with_price_range"] += 1
    if ctx["portability"]:
        result["context_stats"]["with_portability"] += 1
    if ctx["incomplete"]:
        result["context_stats"]["incomplete"] += 1

    result["tagged"] += 1



######Saving
g.serialize("db/abox.ttl", format="turtle")



######SPARQL
query = """
PREFIX mall: <https://fastcampus.co.kr/data_online_ontology2/>

SELECT ?name ?price ?catName
WHERE {
    ?p a mall:Electronics ;
       mall:hasName ?name ;
       mall:hasPrice ?price ;
       mall:belongsToCategory ?c .

    ?c mall:hasCategoryName ?catName .

    FILTER (?price > 2000000)
}
ORDER BY DESC(?price)
LIMIT 5
"""

# 쿼리 프리미엄 제품
q1 = """
PREFIX mall: <https://fastcampus.co.kr/data_online_ontology2/>
SELECT ?name ?price ?priceRange
WHERE {
    ?p mall:hasName ?name ;
        mall:hasPrice ?price ;
        mall:hasPriceRange ?priceRange .
    FILTER (?priceRange = "프리미엄")
}
ORDER BY DESC(?price)
LIMIT 5
"""

# 쿼리 게이밍 용도 + 휴대 가능
q2 = """
PREFIX mall: <https://fastcampus.co.kr/data_online_ontology2/>
SELECT ?name ?purpose ?portability
WHERE {
    ?p mall:hasName ?name ;
        mall:hasPurpose ?purpose ;
        mall:hasPortability ?portability .
    FILTER (?purpose = "게이밍" && ?portability = "휴대 가능")
}
LIMIT 5
"""

results = g.query(query)
for row in results:
    print(row.name, row.price, row.catName)

results1 = g.query(q1)
for row in results1:
    print(row.name, row.price, row.priceRange)

results2 = g.query(q2)
for row in results2:
    print(row.name, row.purpose, row.portability)