"""
电商模拟数据生成脚本 V2 - 大数据量版本

功能:
- 生成约 200 万条订单数据
- 时间范围: 2023-01-01 ~ 2025-11-27
- 支持批量插入，性能优化
- 数据分布模拟真实业务场景

Author: CYJ
Time: 2025-11-27
"""

import os
import random
import string
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Any
import pymysql
from tqdm import tqdm
from dotenv import load_dotenv

# ============================================================
# 配置加载
# ============================================================

# 加载项目根目录的 .env 文件
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))  # chatbi-backend/
env_path = os.path.join(project_root, ".env")

if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
    print(f"[INFO] 已加载配置文件: {env_path}")
else:
    load_dotenv()
    print(f"[WARN] 未找到 .env 文件，将使用环境变量或默认值")

# 从环境变量读取数据库配置
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DB", "chatbi"),
    "charset": "utf8mb4",
}

# 配置区
CONFIG = {
    "n_users": 100_000,        # 10万用户
    "n_shops": 500,            # 500店铺
    "n_products": 20_000,      # 2万商品
    "n_orders": 2_000_000,     # 200万订单
    "batch_size": 10_000,      # 批量插入大小
}

# 时间范围配置
DATE_START = datetime(2023, 1, 1, 0, 0, 0)
DATE_END = datetime(2025, 11, 27, 23, 59, 59)

# ============================================================
# 基础数据定义
# ============================================================

# 扩展的地区数据（50个城市）
REGIONS_DATA = [
    # 一线城市
    ("中国", "北京市", "北京市", "tier1"),
    ("中国", "上海市", "上海市", "tier1"),
    ("中国", "广东省", "广州市", "tier1"),
    ("中国", "广东省", "深圳市", "tier1"),
    # 新一线城市
    ("中国", "四川省", "成都市", "tier2"),
    ("中国", "浙江省", "杭州市", "tier2"),
    ("中国", "重庆市", "重庆市", "tier2"),
    ("中国", "湖北省", "武汉市", "tier2"),
    ("中国", "陕西省", "西安市", "tier2"),
    ("中国", "江苏省", "苏州市", "tier2"),
    ("中国", "江苏省", "南京市", "tier2"),
    ("中国", "天津市", "天津市", "tier2"),
    ("中国", "河南省", "郑州市", "tier2"),
    ("中国", "湖南省", "长沙市", "tier2"),
    ("中国", "山东省", "青岛市", "tier2"),
    ("中国", "辽宁省", "沈阳市", "tier2"),
    ("中国", "浙江省", "宁波市", "tier2"),
    ("中国", "福建省", "厦门市", "tier2"),
    # 二三线城市
    ("中国", "广东省", "东莞市", "tier3"),
    ("中国", "广东省", "佛山市", "tier3"),
    ("中国", "山东省", "济南市", "tier3"),
    ("中国", "河北省", "石家庄市", "tier3"),
    ("中国", "吉林省", "长春市", "tier3"),
    ("中国", "黑龙江省", "哈尔滨市", "tier3"),
    ("中国", "江苏省", "无锡市", "tier3"),
    ("中国", "福建省", "福州市", "tier3"),
    ("中国", "安徽省", "合肥市", "tier3"),
    ("中国", "江西省", "南昌市", "tier3"),
    ("中国", "云南省", "昆明市", "tier3"),
    ("中国", "贵州省", "贵阳市", "tier3"),
    ("中国", "广西壮族自治区", "南宁市", "tier3"),
    ("中国", "海南省", "海口市", "tier3"),
    ("中国", "甘肃省", "兰州市", "tier3"),
    ("中国", "山西省", "太原市", "tier3"),
    ("中国", "内蒙古自治区", "呼和浩特市", "tier3"),
    ("中国", "新疆维吾尔自治区", "乌鲁木齐市", "tier3"),
    # 其他城市
    ("中国", "江苏省", "常州市", "other"),
    ("中国", "江苏省", "徐州市", "other"),
    ("中国", "浙江省", "温州市", "other"),
    ("中国", "浙江省", "嘉兴市", "other"),
    ("中国", "山东省", "烟台市", "other"),
    ("中国", "山东省", "潍坊市", "other"),
    ("中国", "河南省", "洛阳市", "other"),
    ("中国", "河北省", "唐山市", "other"),
    ("中国", "广东省", "珠海市", "other"),
    ("中国", "广东省", "惠州市", "other"),
    ("中国", "湖北省", "宜昌市", "other"),
    ("中国", "四川省", "绵阳市", "other"),
    ("中国", "辽宁省", "大连市", "tier2"),
    ("中国", "江苏省", "扬州市", "other"),
]

# 渠道数据
CHANNELS_DATA = [
    ("web", "官网", "owned"),
    ("app", "APP", "owned"),
    ("mini_program", "小程序", "owned"),
    ("ad", "广告投放", "paid"),
    ("seo", "搜索引擎", "organic"),
    ("social", "社交媒体", "organic"),
]

# 类目数据（三级类目）
CATEGORIES_LEVEL1 = ["电子产品", "家用电器", "服饰鞋包", "美妆个护", "日用百货", "食品饮料", "母婴用品", "运动户外"]

CATEGORIES_LEVEL2 = {
    "电子产品": ["手机", "电脑", "平板", "耳机", "智能手表"],
    "家用电器": ["电视", "空调", "冰箱", "洗衣机", "厨房电器"],
    "服饰鞋包": ["男装", "女装", "童装", "鞋靴", "箱包"],
    "美妆个护": ["护肤", "彩妆", "香水", "个人护理", "美发护发"],
    "日用百货": ["清洁用品", "纸品", "厨具", "收纳整理", "家居饰品"],
    "食品饮料": ["零食", "饮料", "生鲜", "粮油调味", "保健食品"],
    "母婴用品": ["奶粉", "尿裤", "童装童鞋", "玩具", "孕妈用品"],
    "运动户外": ["运动服饰", "运动鞋", "健身器材", "户外装备", "球类运动"],
}

# 品牌数据
BRANDS = [
    "华为", "苹果", "小米", "OPPO", "vivo", "联想", "戴尔", "惠普",
    "海尔", "美的", "格力", "西门子", "松下", "索尼", "三星",
    "耐克", "阿迪达斯", "李宁", "安踏", "特步", "优衣库", "ZARA",
    "欧莱雅", "兰蔻", "雅诗兰黛", "SK-II", "资生堂",
    "伊利", "蒙牛", "农夫山泉", "可口可乐", "百事",
    "帮宝适", "花王", "贝亲", "好孩子",
    "无品牌",
]

# 物流商数据
LOGISTICS_PROVIDERS = [
    (1, "顺丰速运", "SF", "95338", "express"),
    (2, "中通快递", "ZTO", "95311", "standard"),
    (3, "圆通速递", "YTO", "95554", "standard"),
    (4, "韵达快递", "YD", "95546", "standard"),
    (5, "申通快递", "STO", "95543", "economy"),
    (6, "京东物流", "JD", "950616", "express"),
    (7, "菜鸟驿站", "CAINIAO", "95187", "standard"),
    (8, "极兔速递", "JT", "95820", "economy"),
]

# 优惠券数据
COUPONS_DATA = [
    ("满100减10", "full_reduction", 100, 10, None, "all"),
    ("满200减30", "full_reduction", 200, 30, None, "all"),
    ("满500减80", "full_reduction", 500, 80, None, "all"),
    ("满1000减150", "full_reduction", 1000, 150, None, "all"),
    ("全场95折", "discount", None, None, 0.95, "all"),
    ("全场9折", "discount", None, None, 0.90, "all"),
    ("全场85折", "discount", None, None, 0.85, "all"),
    ("新人专享8折", "discount", None, None, 0.80, "all"),
]

# ============================================================
# 工具函数
# ============================================================

def random_datetime(start: datetime, end: datetime) -> datetime:
    """生成随机时间"""
    delta = end - start
    seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=seconds)

def random_datetime_after(base: datetime, max_days: int = 30) -> datetime:
    """生成 base 之后的随机时间，不超过 DATE_END"""
    end = min(base + timedelta(days=max_days), DATE_END)
    if base >= end:
        return base
    return random_datetime(base, end)

def random_code(prefix: str, length: int = 8) -> str:
    """生成随机编码"""
    body = "".join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{body}"

def get_seasonal_weight(dt: datetime) -> float:
    """根据日期返回季节性权重（模拟促销季）"""
    month, day = dt.month, dt.day
    # 双11
    if month == 11 and 1 <= day <= 15:
        return 3.0
    # 618
    if month == 6 and 10 <= day <= 20:
        return 2.5
    # 双12
    if month == 12 and 10 <= day <= 15:
        return 2.0
    # 春节前
    if month == 1 and day >= 15:
        return 1.8
    # 年底
    if month == 12:
        return 1.5
    return 1.0

def batch_insert(cursor, sql: str, data: List[Tuple], batch_size: int = 10000, desc: str = "Inserting"):
    """批量插入数据"""
    total = len(data)
    for i in tqdm(range(0, total, batch_size), desc=desc):
        batch = data[i:i + batch_size]
        cursor.executemany(sql, batch)

# ============================================================
# 数据生成函数
# ============================================================

def truncate_tables(cursor) -> None:
    """清空所有表"""
    tables = [
        "shipment_tracking_events", "shipment_items", "shipments", "logistics_providers",
        "order_coupons", "user_coupons", "coupons",
        "refunds", "payments", "order_items", "orders",
        "products", "categories", "shops", "users",
        "dim_channel", "dim_region",
    ]
    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in tables:
        cursor.execute(f"TRUNCATE TABLE {t}")
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")

def gen_dim_region(cursor) -> List[int]:
    """生成地区维度数据"""
    data = [(i + 1, *row) for i, row in enumerate(REGIONS_DATA)]
    cursor.executemany(
        "INSERT INTO dim_region (id, country, province, city, city_level) VALUES (%s,%s,%s,%s,%s)",
        data
    )
    return [d[0] for d in data]

def gen_dim_channel(cursor) -> List[str]:
    """生成渠道维度数据"""
    cursor.executemany(
        "INSERT INTO dim_channel (channel_code, channel_name, channel_type) VALUES (%s,%s,%s)",
        CHANNELS_DATA
    )
    return [c[0] for c in CHANNELS_DATA]

def gen_users(cursor, region_ids: List[int], channel_codes: List[str], n_users: int) -> Dict[int, datetime]:
    """
    生成用户数据
    返回: {user_id: registered_at} 映射
    """
    users = []
    user_registered = {}
    
    for uid in tqdm(range(1, n_users + 1), desc="Generating users"):
        username = f"user_{uid:06d}"
        email = f"user_{uid:06d}@example.com"
        phone = f"1{random.randint(3000000000, 9999999999)}"[:11]
        
        # 用户注册时间随机分布，但模拟增长趋势（后期用户更多）
        # 使用二次分布使后期用户更密集
        progress = random.random() ** 0.7  # 0.7 指数使分布偏向后期
        registered_at = DATE_START + timedelta(
            seconds=int(progress * (DATE_END - DATE_START).total_seconds())
        )
        
        channel = random.choice(channel_codes)
        region_id = random.choice(region_ids)
        # 会员等级分布: 0=60%, 1=25%, 2=10%, 3=5%
        level = random.choices([0, 1, 2, 3], weights=[60, 25, 10, 5], k=1)[0]
        
        users.append((uid, username, email, phone, registered_at, channel, region_id, level))
        user_registered[uid] = registered_at
    
    batch_insert(
        cursor,
        """INSERT INTO users (id, username, email, phone, registered_at, register_channel_code, region_id, level)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        users,
        desc="Inserting users"
    )
    
    return user_registered

def gen_shops(cursor, user_ids: List[int], region_ids: List[int], n_shops: int) -> List[int]:
    """生成店铺数据"""
    shops = []
    
    for sid in range(1, n_shops + 1):
        name = f"店铺_{sid:04d}"
        owner_user_id = random.choice(user_ids)
        region_id = random.choice(region_ids)
        # 店铺开业时间在数据范围内
        opened_at = random_datetime(DATE_START, DATE_END - timedelta(days=30))
        shop_type = random.choices(["self", "third_party"], weights=[30, 70], k=1)[0]
        status = random.choices(["active", "inactive"], weights=[95, 5], k=1)[0]
        
        shops.append((sid, name, owner_user_id, shop_type, region_id, opened_at, status))
    
    cursor.executemany(
        """INSERT INTO shops (id, name, owner_user_id, shop_type, region_id, opened_at, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        shops
    )
    
    return [s[0] for s in shops]

def gen_categories(cursor) -> List[Tuple[int, int]]:
    """
    生成三级类目数据
    返回: [(category_id, level), ...]
    """
    categories = []
    cid = 1
    
    # 一级类目
    level1_ids = {}
    for name in CATEGORIES_LEVEL1:
        categories.append((cid, None, name, 1))
        level1_ids[name] = cid
        cid += 1
    
    # 二级类目
    level2_ids = {}
    for parent_name, children in CATEGORIES_LEVEL2.items():
        parent_id = level1_ids[parent_name]
        for child_name in children:
            categories.append((cid, parent_id, child_name, 2))
            level2_ids[child_name] = cid
            cid += 1
    
    # 三级类目（为每个二级类目生成 2-3 个三级类目）
    for level2_name, level2_id in level2_ids.items():
        n_level3 = random.randint(2, 3)
        for i in range(n_level3):
            name = f"{level2_name}_{i+1}"
            categories.append((cid, level2_id, name, 3))
            cid += 1
    
    cursor.executemany(
        "INSERT INTO categories (id, parent_id, name, level) VALUES (%s,%s,%s,%s)",
        categories
    )
    
    return [(c[0], c[3]) for c in categories]  # (id, level)

def gen_products(cursor, category_data: List[Tuple[int, int]], shop_ids: List[int], n_products: int) -> Dict[int, float]:
    """
    生成商品数据
    返回: {product_id: price} 映射
    """
    products = []
    price_map = {}
    
    # 只使用三级类目（level=3）
    level3_categories = [c[0] for c in category_data if c[1] == 3]
    if not level3_categories:
        level3_categories = [c[0] for c in category_data if c[1] == 2]
    
    for pid in tqdm(range(1, n_products + 1), desc="Generating products"):
        category_id = random.choice(level3_categories)
        shop_id = random.choice(shop_ids)
        name = f"商品_{category_id}_{pid:06d}"
        brand = random.choice(BRANDS)
        # 价格分布：大部分商品 50-500，少数高价商品
        price = round(random.choices(
            [random.uniform(10, 100), random.uniform(100, 500), random.uniform(500, 2000), random.uniform(2000, 10000)],
            weights=[30, 40, 25, 5],
            k=1
        )[0], 2)
        status = random.choices(["on_sale", "off_sale"], weights=[90, 10], k=1)[0]
        created_at = random_datetime(DATE_START, DATE_END - timedelta(days=7))
        
        products.append((pid, name, category_id, shop_id, brand, price, status, created_at))
        price_map[pid] = price
    
    batch_insert(
        cursor,
        """INSERT INTO products (id, name, category_id, shop_id, brand, price, status, created_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        products,
        desc="Inserting products"
    )
    
    return price_map

def gen_orders_and_items(
    cursor,
    user_registered: Dict[int, datetime],
    shop_ids: List[int],
    product_ids: List[int],
    product_price_map: Dict[int, float],
    region_ids: List[int],
    channel_codes: List[str],
    n_orders: int
) -> List[Dict]:
    """生成订单和订单明细"""
    user_ids = list(user_registered.keys())
    orders = []
    items = []
    order_id = 1
    order_item_id = 1
    
    # 按批次生成订单
    batch_size = CONFIG["batch_size"]
    
    for batch_start in tqdm(range(0, n_orders, batch_size), desc="Generating orders"):
        batch_orders = []
        batch_items = []
        batch_end = min(batch_start + batch_size, n_orders)
        
        for _ in range(batch_end - batch_start):
            user_id = random.choice(user_ids)
            user_reg_time = user_registered[user_id]
            shop_id = random.choice(shop_ids)
            channel = random.choice(channel_codes)
            region_id = random.choice(region_ids)
            
            # 订单时间：用户注册后的随机时间
            order_time = random_datetime_after(user_reg_time, max_days=365 * 3)
            
            # 订单状态分布
            status = random.choices(
                ["created", "paid", "shipped", "completed", "cancelled", "refunded"],
                weights=[5, 20, 15, 45, 10, 5],
                k=1
            )[0]
            
            paid_at = None
            if status in ("paid", "shipped", "completed", "refunded"):
                paid_at = order_time + timedelta(hours=random.randint(0, 24))
            
            order_no = random_code("ORD", 12)
            
            # 生成订单明细
            n_items = random.choices([1, 2, 3, 4, 5], weights=[50, 25, 15, 7, 3], k=1)[0]
            total = 0.0
            
            for _ in range(n_items):
                product_id = random.choice(product_ids)
                quantity = random.choices([1, 2, 3], weights=[70, 25, 5], k=1)[0]
                unit_price = product_price_map[product_id]
                subtotal = round(unit_price * quantity, 2)
                total += subtotal
                
                batch_items.append((order_item_id, order_id, product_id, quantity, unit_price, subtotal))
                order_item_id += 1
            
            total = round(total, 2)
            discount = 0.0
            pay_amount = total
            
            batch_orders.append({
                "id": order_id,
                "order_no": order_no,
                "user_id": user_id,
                "shop_id": shop_id,
                "channel": channel,
                "region_id": region_id,
                "status": status,
                "total_amount": total,
                "discount_amount": discount,
                "pay_amount": pay_amount,
                "created_at": order_time,
                "paid_at": paid_at,
            })
            
            order_id += 1
        
        # 批量插入订单
        order_rows = [
            (o["id"], o["order_no"], o["user_id"], o["shop_id"], o["channel"], o["region_id"],
             o["status"], o["total_amount"], o["discount_amount"], o["pay_amount"],
             o["created_at"], o["paid_at"])
            for o in batch_orders
        ]
        
        cursor.executemany(
            """INSERT INTO orders (id, order_no, user_id, shop_id, order_channel_code, shipping_region_id,
               status, total_amount, discount_amount, pay_amount, created_at, paid_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            order_rows
        )
        
        cursor.executemany(
            """INSERT INTO order_items (id, order_id, product_id, quantity, unit_price, subtotal_amount)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            batch_items
        )
        
        orders.extend(batch_orders)
        items.extend(batch_items)
    
    return orders

def gen_payments_and_refunds(cursor, orders: List[Dict]) -> None:
    """生成支付和退款记录"""
    payments = []
    refunds = []
    pay_id = 1
    refund_id = 1
    
    for o in tqdm(orders, desc="Generating payments"):
        if o["status"] in ("paid", "shipped", "completed", "refunded"):
            pay_status = "success"
            pay_method = random.choices(
                ["alipay", "wechat", "card", "other"],
                weights=[40, 45, 10, 5],
                k=1
            )[0]
            pay_amount = o["pay_amount"]
            paid_at = o["paid_at"] or o["created_at"]
            
            payments.append((pay_id, o["id"], pay_method, pay_amount, pay_status, paid_at))
            
            if o["status"] == "refunded" and pay_amount > 0:
                refund_amount = round(pay_amount * random.uniform(0.3, 1.0), 2)
                refund_status = "success"
                refunded_at = paid_at + timedelta(days=random.randint(1, 14))
                reasons = ["质量问题", "不想要了", "发错货", "尺码不合适", "与描述不符"]
                
                refunds.append((
                    refund_id, o["id"], pay_id, refund_amount,
                    random.choice(reasons), refund_status, refunded_at
                ))
                refund_id += 1
            
            pay_id += 1
    
    if payments:
        batch_insert(
            cursor,
            """INSERT INTO payments (id, order_id, pay_method, pay_amount, pay_status, paid_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            payments,
            desc="Inserting payments"
        )
    
    if refunds:
        batch_insert(
            cursor,
            """INSERT INTO refunds (id, order_id, payment_id, refund_amount, refund_reason, refund_status, refunded_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            refunds,
            desc="Inserting refunds"
        )

def gen_coupons_and_relations(cursor, user_ids: List[int], orders: List[Dict]) -> None:
    """生成优惠券和使用记录"""
    coupons = []
    coupon_id = 1
    valid_from = DATE_START
    valid_to = DATE_END + timedelta(days=180)
    
    for name, ctype, threshold, amount, rate, scope in COUPONS_DATA:
        code = random_code("CP", 10)
        coupons.append((
            coupon_id, code, ctype, threshold, amount, rate,
            valid_from, valid_to, scope, None
        ))
        coupon_id += 1
    
    cursor.executemany(
        """INSERT INTO coupons (id, code, type, threshold_amount, discount_amount, discount_rate,
           valid_from, valid_to, scope, shop_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        coupons
    )
    
    coupon_ids = [c[0] for c in coupons]
    
    # 用户领券（30%的用户领券）
    user_coupon_rows = []
    user_coupon_id = 1
    sampled_users = random.sample(user_ids, k=int(len(user_ids) * 0.3))
    
    for uid in tqdm(sampled_users, desc="Generating user_coupons"):
        n = random.randint(1, 5)
        for _ in range(n):
            cid = random.choice(coupon_ids)
            status = random.choices(["unused", "used", "expired"], weights=[40, 40, 20], k=1)[0]
            received_at = random_datetime(DATE_START, DATE_END)
            used_at = None
            if status == "used":
                used_at = received_at + timedelta(days=random.randint(0, 30))
            user_coupon_rows.append((user_coupon_id, uid, cid, status, received_at, used_at))
            user_coupon_id += 1
    
    if user_coupon_rows:
        batch_insert(
            cursor,
            """INSERT INTO user_coupons (id, user_id, coupon_id, status, received_at, used_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            user_coupon_rows,
            desc="Inserting user_coupons"
        )
    
    # 订单用券（20%的订单使用优惠券）
    order_coupon_rows = []
    order_coupon_id = 1
    applicable_orders = [o for o in orders if o["total_amount"] >= 50]
    sampled_orders = random.sample(applicable_orders, k=int(len(applicable_orders) * 0.2))
    
    for o in tqdm(sampled_orders, desc="Generating order_coupons"):
        cid = random.choice(coupon_ids)
        max_discount = min(o["total_amount"] * 0.3, 200)
        discount = round(random.uniform(5, max_discount), 2)
        order_coupon_rows.append((order_coupon_id, o["id"], cid, discount))
        order_coupon_id += 1
    
    if order_coupon_rows:
        batch_insert(
            cursor,
            """INSERT INTO order_coupons (id, order_id, coupon_id, discount_amount)
               VALUES (%s,%s,%s,%s)""",
            order_coupon_rows,
            desc="Inserting order_coupons"
        )

def gen_logistics(cursor) -> List[int]:
    """生成物流承运商数据"""
    cursor.executemany(
        """INSERT INTO logistics_providers (id, name, code, contact_phone, service_level)
           VALUES (%s,%s,%s,%s,%s)""",
        LOGISTICS_PROVIDERS
    )
    return [p[0] for p in LOGISTICS_PROVIDERS]

def gen_shipments_and_events(cursor, provider_ids: List[int]) -> None:
    """生成发货单和物流轨迹"""
    cursor.execute(
        "SELECT id, created_at FROM orders WHERE status IN ('shipped','completed','refunded')"
    )
    orders = cursor.fetchall()
    
    shipments = []
    events = []
    shipment_id = 1
    event_id = 1
    
    for order_id, created_at in tqdm(orders, desc="Generating shipments"):
        provider_id = random.choice(provider_ids)
        shipped_at = created_at + timedelta(days=random.randint(1, 3))
        delivered_at = shipped_at + timedelta(days=random.randint(1, 7))
        
        # 确保不超过 DATE_END
        if shipped_at > DATE_END:
            shipped_at = DATE_END - timedelta(days=3)
        if delivered_at > DATE_END:
            delivered_at = DATE_END
        
        status = random.choices(
            ["shipped", "in_transit", "delivered", "returned", "lost"],
            weights=[5, 20, 70, 4, 1],
            k=1
        )[0]
        
        tracking_no = random_code("TRK", 12)
        
        shipments.append((
            shipment_id, order_id, provider_id, tracking_no,
            shipped_at, delivered_at if status == "delivered" else None, status
        ))
        
        # 物流轨迹事件
        event_time = shipped_at
        event_statuses = ["已揽件", "运输中", "派送中"]
        if status == "delivered":
            event_statuses.append("已签收")
        
        for s in event_statuses:
            events.append((event_id, shipment_id, event_time, s, None, f"{s}，运单号 {tracking_no}"))
            event_id += 1
            event_time += timedelta(hours=random.randint(6, 48))
        
        shipment_id += 1
    
    if shipments:
        batch_insert(
            cursor,
            """INSERT INTO shipments (id, order_id, logistics_provider_id, tracking_no,
               shipped_at, delivered_at, status) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            shipments,
            desc="Inserting shipments"
        )
    
    if events:
        batch_insert(
            cursor,
            """INSERT INTO shipment_tracking_events (id, shipment_id, event_time, event_status, location, description)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            events,
            desc="Inserting tracking events"
        )
    
    # 发货明细
    cursor.execute("SELECT id, order_id FROM shipments")
    shipment_rows = cursor.fetchall()
    order_to_shipment = {order_id: sid for sid, order_id in shipment_rows}
    
    cursor.execute("SELECT id, order_id FROM order_items")
    order_items = cursor.fetchall()
    
    shipment_items = []
    shipment_item_id = 1
    
    for order_item_id, order_id in order_items:
        shipment_id = order_to_shipment.get(order_id)
        if shipment_id:
            shipment_items.append((shipment_item_id, shipment_id, order_item_id, 1))
            shipment_item_id += 1
    
    if shipment_items:
        batch_insert(
            cursor,
            """INSERT INTO shipment_items (id, shipment_id, order_item_id, quantity)
               VALUES (%s,%s,%s,%s)""",
            shipment_items,
            desc="Inserting shipment items"
        )

# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 60)
    print("电商模拟数据生成 V2")
    print("=" * 60)
    print(f"数据量配置: {CONFIG}")
    print(f"时间范围: {DATE_START} ~ {DATE_END}")
    print(f"数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']} (user: {DB_CONFIG['user']})")
    print("=" * 60)
    
    print("\n[INFO] Connecting to MySQL ...")
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        print("\n[INFO] Truncating existing tables ...")
        truncate_tables(cursor)
        conn.commit()
        
        print("\n[INFO] Generating dim_region ...")
        region_ids = gen_dim_region(cursor)
        print(f"  -> {len(region_ids)} regions")
        conn.commit()
        
        print("\n[INFO] Generating dim_channel ...")
        channel_codes = gen_dim_channel(cursor)
        print(f"  -> {len(channel_codes)} channels")
        conn.commit()
        
        print("\n[INFO] Generating users ...")
        user_registered = gen_users(cursor, region_ids, channel_codes, CONFIG["n_users"])
        print(f"  -> {len(user_registered)} users")
        conn.commit()
        
        print("\n[INFO] Generating shops ...")
        shop_ids = gen_shops(cursor, list(user_registered.keys()), region_ids, CONFIG["n_shops"])
        print(f"  -> {len(shop_ids)} shops")
        conn.commit()
        
        print("\n[INFO] Generating categories ...")
        category_data = gen_categories(cursor)
        print(f"  -> {len(category_data)} categories")
        conn.commit()
        
        print("\n[INFO] Generating products ...")
        product_price_map = gen_products(cursor, category_data, shop_ids, CONFIG["n_products"])
        print(f"  -> {len(product_price_map)} products")
        conn.commit()
        
        print("\n[INFO] Generating orders and order_items ...")
        orders = gen_orders_and_items(
            cursor,
            user_registered,
            shop_ids,
            list(product_price_map.keys()),
            product_price_map,
            region_ids,
            channel_codes,
            CONFIG["n_orders"]
        )
        print(f"  -> {len(orders)} orders")
        conn.commit()
        
        print("\n[INFO] Generating payments and refunds ...")
        gen_payments_and_refunds(cursor, orders)
        conn.commit()
        
        print("\n[INFO] Generating coupons and relations ...")
        gen_coupons_and_relations(cursor, list(user_registered.keys()), orders)
        conn.commit()
        
        print("\n[INFO] Generating logistics providers ...")
        provider_ids = gen_logistics(cursor)
        print(f"  -> {len(provider_ids)} providers")
        conn.commit()
        
        print("\n[INFO] Generating shipments and tracking events ...")
        gen_shipments_and_events(cursor, provider_ids)
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✓ Mock data generation completed!")
        print("=" * 60)
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()
