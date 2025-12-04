-- 电商示例库 DDL（多领域、多维度）
-- chatbi

-- 说明：
-- 1. 覆盖用户/会员、商品/品类、店铺、交易订单、支付退款、营销优惠券、渠道与地区维度等多个子领域；
-- 2. 所有表和字段均带有中文注释，便于后续元数据抽取、向量化和知识图谱构建；
-- 3. 外键命名规范为 fk_源表_目标表_字段，便于自动化解析。


USE chatbi;

-- =========================================================
-- 维度域：地区维度
-- =========================================================

DROP TABLE IF EXISTS dim_region;
CREATE TABLE dim_region (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '地区维度ID',
  country VARCHAR(64) NOT NULL COMMENT '国家名称，例如中国',
  province VARCHAR(64) NOT NULL COMMENT '省/州，例如浙江省',
  city VARCHAR(64) NOT NULL COMMENT '城市名称，例如杭州市',
  city_level ENUM('tier1','tier2','tier3','other') NOT NULL DEFAULT 'other' COMMENT '城市等级: tier1=一线城市, tier2=新一线/二线城市, tier3=三线城市, other=其他',
  PRIMARY KEY (id),
  KEY idx_dim_region_country_province_city (country, province, city)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='地区维度表';

-- =========================================================
-- 维度域：渠道维度（注册渠道、下单渠道等统一编码）
-- =========================================================

DROP TABLE IF EXISTS dim_channel;
CREATE TABLE dim_channel (
  channel_code VARCHAR(32) NOT NULL COMMENT '渠道编码，例如 web/app/mini_program',
  channel_name VARCHAR(64) NOT NULL COMMENT '渠道名称，例如官网、App、小程序',
  channel_type VARCHAR(32) NOT NULL COMMENT '渠道类型，例如 owned/paid/organic',
  PRIMARY KEY (channel_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='渠道维度表';

-- =========================================================
-- 店铺域：店铺基础信息
-- =========================================================

DROP TABLE IF EXISTS shops;
CREATE TABLE shops (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '店铺ID',
  name VARCHAR(128) NOT NULL COMMENT '店铺名称',
  owner_user_id BIGINT UNSIGNED NULL COMMENT '店主用户ID，对应 users.id',
  shop_type ENUM('self','third_party') NOT NULL DEFAULT 'self' COMMENT '店铺类型: self=平台自营, third_party=第三方商家',
  region_id BIGINT UNSIGNED NULL COMMENT '店铺所在地区，对应 dim_region.id',
  opened_at DATETIME NOT NULL COMMENT '店铺开店时间',
  status ENUM('active','inactive') NOT NULL DEFAULT 'active' COMMENT '店铺状态: active=正常营业, inactive=停用/关店',
  PRIMARY KEY (id),
  KEY idx_shops_owner_user (owner_user_id),
  KEY idx_shops_region (region_id),
  CONSTRAINT fk_shops_dim_region_region_id
    FOREIGN KEY (region_id) REFERENCES dim_region(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='店铺表';

-- 注意：由于 shops 依赖 users，下面先定义 users 表，再通过 ALTER TABLE 添加外键更安全；

-- =========================================================
-- 用户域：用户/会员基础信息
-- =========================================================

DROP TABLE IF EXISTS users;
CREATE TABLE users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  username VARCHAR(64) NOT NULL COMMENT '用户名/登录名',
  email VARCHAR(128) NULL COMMENT '邮箱地址',
  phone VARCHAR(20) NULL COMMENT '手机号',
  registered_at DATETIME NOT NULL COMMENT '注册时间',
  register_channel_code VARCHAR(32) NOT NULL COMMENT '注册渠道编码，对应 dim_channel.channel_code',
  region_id BIGINT UNSIGNED NULL COMMENT '用户所在地区，对应 dim_region.id',
  level TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '会员等级: 0=普通用户, 1=银卡会员, 2=金卡会员, 3=VIP会员',
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_email (email),
  UNIQUE KEY uk_users_phone (phone),
  KEY idx_users_registered_at (registered_at),
  KEY idx_users_region (region_id),
  KEY idx_users_register_channel (register_channel_code),
  CONSTRAINT fk_users_dim_region_region_id
    FOREIGN KEY (region_id) REFERENCES dim_region(id),
  CONSTRAINT fk_users_dim_channel_register_channel_code
    FOREIGN KEY (register_channel_code) REFERENCES dim_channel(channel_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 现在通过 ALTER TABLE 安全地给 shops 增加外键（避免引用未定义的 users 表）

ALTER TABLE shops
  ADD CONSTRAINT fk_shops_users_owner_user_id
    FOREIGN KEY (owner_user_id) REFERENCES users(id);

-- =========================================================
-- 商品域：类目与商品
-- =========================================================

DROP TABLE IF EXISTS categories;
CREATE TABLE categories (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '类目ID',
  parent_id BIGINT UNSIGNED NULL COMMENT '父类目ID，自关联 categories.id',
  name VARCHAR(64) NOT NULL COMMENT '类目名称，例如手机、家电',
  level TINYINT UNSIGNED NOT NULL COMMENT '类目层级：1=一级类目，2=二级类目，3=三级类目',
  PRIMARY KEY (id),
  KEY idx_categories_parent (parent_id),
  CONSTRAINT fk_categories_categories_parent_id
    FOREIGN KEY (parent_id) REFERENCES categories(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品类目表';

DROP TABLE IF EXISTS products;
CREATE TABLE products (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '商品ID',
  name VARCHAR(128) NOT NULL COMMENT '商品名称',
  category_id BIGINT UNSIGNED NOT NULL COMMENT '所属类目ID，对应 categories.id',
  shop_id BIGINT UNSIGNED NOT NULL COMMENT '所属店铺ID，对应 shops.id',
  brand VARCHAR(64) NULL COMMENT '品牌名称',
  price DECIMAL(18,2) NOT NULL COMMENT '标价，单位元',
  status ENUM('on_sale','off_sale') NOT NULL DEFAULT 'on_sale' COMMENT '上下架状态: on_sale=在售, off_sale=已下架',
  created_at DATETIME NOT NULL COMMENT '商品创建时间',
  PRIMARY KEY (id),
  KEY idx_products_category (category_id),
  KEY idx_products_shop (shop_id),
  KEY idx_products_status (status),
  CONSTRAINT fk_products_categories_category_id
    FOREIGN KEY (category_id) REFERENCES categories(id),
  CONSTRAINT fk_products_shops_shop_id
    FOREIGN KEY (shop_id) REFERENCES shops(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- =========================================================
-- 交易域：订单与订单明细
-- =========================================================

DROP TABLE IF EXISTS orders;
CREATE TABLE orders (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '订单ID',
  order_no VARCHAR(64) NOT NULL COMMENT '订单号，业务唯一编码',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '下单用户ID，对应 users.id',
  shop_id BIGINT UNSIGNED NOT NULL COMMENT '所属店铺ID，对应 shops.id',
  order_channel_code VARCHAR(32) NOT NULL COMMENT '下单渠道编码，对应 dim_channel.channel_code',
  shipping_region_id BIGINT UNSIGNED NULL COMMENT '收货地区ID，对应 dim_region.id',
  status ENUM('created','paid','shipped','completed','cancelled','refunded') NOT NULL DEFAULT 'created' COMMENT '订单状态: created=已创建/待付款, paid=已付款/待发货, shipped=已发货, completed=已完成, cancelled=已取消, refunded=已退款',
  total_amount DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '订单商品总金额（未扣减优惠）',
  discount_amount DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '订单总优惠金额',
  pay_amount DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '订单实付金额（total_amount - discount_amount）',
  created_at DATETIME NOT NULL COMMENT '下单时间',
  paid_at DATETIME NULL COMMENT '支付时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_orders_order_no (order_no),
  KEY idx_orders_user (user_id),
  KEY idx_orders_shop (shop_id),
  KEY idx_orders_status (status),
  KEY idx_orders_created_at (created_at),
  KEY idx_orders_channel (order_channel_code),
  KEY idx_orders_shipping_region (shipping_region_id),
  CONSTRAINT fk_orders_users_user_id
    FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_orders_shops_shop_id
    FOREIGN KEY (shop_id) REFERENCES shops(id),
  CONSTRAINT fk_orders_dim_channel_order_channel_code
    FOREIGN KEY (order_channel_code) REFERENCES dim_channel(channel_code),
  CONSTRAINT fk_orders_dim_region_shipping_region_id
    FOREIGN KEY (shipping_region_id) REFERENCES dim_region(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';

DROP TABLE IF EXISTS order_items;
CREATE TABLE order_items (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '订单明细ID',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID，对应 orders.id',
  product_id BIGINT UNSIGNED NOT NULL COMMENT '商品ID，对应 products.id',
  quantity INT NOT NULL COMMENT '购买数量',
  unit_price DECIMAL(18,2) NOT NULL COMMENT '成交单价，单位元',
  subtotal_amount DECIMAL(18,2) NOT NULL COMMENT '明细小计金额，quantity * unit_price',
  PRIMARY KEY (id),
  KEY idx_order_items_order (order_id),
  KEY idx_order_items_product (product_id),
  CONSTRAINT fk_order_items_orders_order_id
    FOREIGN KEY (order_id) REFERENCES orders(id),
  CONSTRAINT fk_order_items_products_product_id
    FOREIGN KEY (product_id) REFERENCES products(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细表';

-- =========================================================
-- 支付与退款域
-- =========================================================

DROP TABLE IF EXISTS payments;
CREATE TABLE payments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '支付记录ID',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '对应订单ID，对应 orders.id',
  pay_method ENUM('alipay','wechat','card','other') NOT NULL COMMENT '支付方式: alipay=支付宝, wechat=微信支付, card=银行卡, other=其他方式',
  pay_amount DECIMAL(18,2) NOT NULL COMMENT '支付金额，单位元',
  pay_status ENUM('pending','success','failed') NOT NULL DEFAULT 'pending' COMMENT '支付状态: pending=待支付, success=支付成功, failed=支付失败',
  paid_at DATETIME NULL COMMENT '支付完成时间',
  PRIMARY KEY (id),
  KEY idx_payments_order (order_id),
  KEY idx_payments_status (pay_status),
  CONSTRAINT fk_payments_orders_order_id
    FOREIGN KEY (order_id) REFERENCES orders(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付记录表';

DROP TABLE IF EXISTS refunds;
CREATE TABLE refunds (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '退款记录ID',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '对应订单ID，对应 orders.id',
  payment_id BIGINT UNSIGNED NOT NULL COMMENT '对应支付记录ID，对应 payments.id',
  refund_amount DECIMAL(18,2) NOT NULL COMMENT '退款金额，单位元',
  refund_reason VARCHAR(255) NULL COMMENT '退款原因描述',
  refund_status ENUM('pending','success','failed') NOT NULL DEFAULT 'pending' COMMENT '退款状态: pending=待退款, success=退款成功, failed=退款失败',
  refunded_at DATETIME NULL COMMENT '退款完成时间',
  PRIMARY KEY (id),
  KEY idx_refunds_order (order_id),
  KEY idx_refunds_payment (payment_id),
  CONSTRAINT fk_refunds_orders_order_id
    FOREIGN KEY (order_id) REFERENCES orders(id),
  CONSTRAINT fk_refunds_payments_payment_id
    FOREIGN KEY (payment_id) REFERENCES payments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='退款记录表';

-- =========================================================
-- 营销域：优惠券与领券/用券
-- =========================================================

DROP TABLE IF EXISTS coupons;
CREATE TABLE coupons (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '优惠券ID',
  code VARCHAR(64) NOT NULL COMMENT '券码，唯一标识一类券',
  type ENUM('full_reduction','discount') NOT NULL COMMENT '优惠类型: full_reduction=满减券, discount=折扣券',
  threshold_amount DECIMAL(18,2) NULL COMMENT '满减门槛金额，type=full_reduction 时生效',
  discount_amount DECIMAL(18,2) NULL COMMENT '满减优惠金额，type=full_reduction 时生效',
  discount_rate DECIMAL(5,2) NULL COMMENT '折扣比例，例如 0.90 表示 9 折，type=discount 时生效',
  valid_from DATETIME NOT NULL COMMENT '优惠券生效时间',
  valid_to DATETIME NOT NULL COMMENT '优惠券失效时间',
  scope ENUM('all','category','product','shop') NOT NULL DEFAULT 'all' COMMENT '适用范围: all=全场通用, category=指定类目, product=指定商品, shop=指定店铺',
  shop_id BIGINT UNSIGNED NULL COMMENT '适用店铺ID，对应 shops.id，仅当 scope=shop 时生效',
  PRIMARY KEY (id),
  UNIQUE KEY uk_coupons_code (code),
  KEY idx_coupons_shop (shop_id),
  CONSTRAINT fk_coupons_shops_shop_id
    FOREIGN KEY (shop_id) REFERENCES shops(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='优惠券表';

DROP TABLE IF EXISTS user_coupons;
CREATE TABLE user_coupons (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户券记录ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID，对应 users.id',
  coupon_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券ID，对应 coupons.id',
  status ENUM('unused','used','expired') NOT NULL DEFAULT 'unused' COMMENT '券状态: unused=未使用, used=已使用, expired=已过期',
  received_at DATETIME NOT NULL COMMENT '领取时间',
  used_at DATETIME NULL COMMENT '使用时间',
  PRIMARY KEY (id),
  KEY idx_user_coupons_user (user_id),
  KEY idx_user_coupons_coupon (coupon_id),
  KEY idx_user_coupons_status (status),
  CONSTRAINT fk_user_coupons_users_user_id
    FOREIGN KEY (user_id) REFERENCES users(id),
  CONSTRAINT fk_user_coupons_coupons_coupon_id
    FOREIGN KEY (coupon_id) REFERENCES coupons(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户领券表';

DROP TABLE IF EXISTS order_coupons;
CREATE TABLE order_coupons (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '订单用券记录ID',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '订单ID，对应 orders.id',
  coupon_id BIGINT UNSIGNED NOT NULL COMMENT '优惠券ID，对应 coupons.id',
  discount_amount DECIMAL(18,2) NOT NULL COMMENT '该券在此订单上的实际优惠金额',
  PRIMARY KEY (id),
  KEY idx_order_coupons_order (order_id),
  KEY idx_order_coupons_coupon (coupon_id),
  CONSTRAINT fk_order_coupons_orders_order_id
    FOREIGN KEY (order_id) REFERENCES orders(id),
  CONSTRAINT fk_order_coupons_coupons_coupon_id
    FOREIGN KEY (coupon_id) REFERENCES coupons(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单用券表';

-- =========================================================
-- 物流域：承运商、发货单与物流轨迹
-- =========================================================

DROP TABLE IF EXISTS logistics_providers;
CREATE TABLE logistics_providers (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '物流承运商ID',
  name VARCHAR(64) NOT NULL COMMENT '物流承运商名称，例如顺丰、中通',
  code VARCHAR(32) NOT NULL COMMENT '承运商编码，内部统一标识',
  contact_phone VARCHAR(20) NULL COMMENT '客服电话/联系号码',
  service_level ENUM('standard','express','same_day','economy') NOT NULL DEFAULT 'standard' COMMENT '服务等级: standard=标准快递, express=加急快递, same_day=当日达, economy=经济快递',
  PRIMARY KEY (id),
  UNIQUE KEY uk_logistics_providers_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='物流承运商表';

DROP TABLE IF EXISTS shipments;
CREATE TABLE shipments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '发货单ID',
  order_id BIGINT UNSIGNED NOT NULL COMMENT '关联订单ID，对应 orders.id',
  logistics_provider_id BIGINT UNSIGNED NOT NULL COMMENT '物流承运商ID，对应 logistics_providers.id',
  tracking_no VARCHAR(64) NOT NULL COMMENT '运单号/快递单号',
  shipped_at DATETIME NOT NULL COMMENT '发货时间',
  delivered_at DATETIME NULL COMMENT '签收时间',
  status ENUM('pending','shipped','in_transit','delivered','returned','lost') NOT NULL DEFAULT 'pending' COMMENT '物流状态: pending=待发货, shipped=已发货, in_transit=运输中, delivered=已签收, returned=已退回, lost=快件丢失',
  PRIMARY KEY (id),
  UNIQUE KEY uk_shipments_tracking_no (tracking_no),
  KEY idx_shipments_order (order_id),
  KEY idx_shipments_provider (logistics_provider_id),
  CONSTRAINT fk_shipments_orders_order_id
    FOREIGN KEY (order_id) REFERENCES orders(id),
  CONSTRAINT fk_shipments_logistics_providers_provider_id
    FOREIGN KEY (logistics_provider_id) REFERENCES logistics_providers(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='发货单表';

DROP TABLE IF EXISTS shipment_items;
CREATE TABLE shipment_items (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '发货明细ID',
  shipment_id BIGINT UNSIGNED NOT NULL COMMENT '发货单ID，对应 shipments.id',
  order_item_id BIGINT UNSIGNED NOT NULL COMMENT '订单明细ID，对应 order_items.id',
  quantity INT NOT NULL COMMENT '本次发货数量',
  PRIMARY KEY (id),
  KEY idx_shipment_items_shipment (shipment_id),
  KEY idx_shipment_items_order_item (order_item_id),
  CONSTRAINT fk_shipment_items_shipments_shipment_id
    FOREIGN KEY (shipment_id) REFERENCES shipments(id),
  CONSTRAINT fk_shipment_items_order_items_order_item_id
    FOREIGN KEY (order_item_id) REFERENCES order_items(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='发货明细表';

DROP TABLE IF EXISTS shipment_tracking_events;
CREATE TABLE shipment_tracking_events (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '物流轨迹事件ID',
  shipment_id BIGINT UNSIGNED NOT NULL COMMENT '发货单ID，对应 shipments.id',
  event_time DATETIME NOT NULL COMMENT '事件时间',
  event_status VARCHAR(64) NOT NULL COMMENT '事件状态/节点，例如已揽收、运输中、派送中、已签收',
  location VARCHAR(128) NULL COMMENT '事件发生地，例如城市/网点',
  description VARCHAR(255) NULL COMMENT '事件描述详情',
  PRIMARY KEY (id),
  KEY idx_shipment_tracking_events_shipment (shipment_id),
  KEY idx_shipment_tracking_events_event_time (event_time),
  CONSTRAINT fk_shipment_tracking_events_shipments_shipment_id
    FOREIGN KEY (shipment_id) REFERENCES shipments(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='物流轨迹事件表';

-- =========================================================
-- 说明：
-- 以上表结构覆盖了以下子领域和常用分析维度：
-- 1）用户/会员：users（维度：地区 dim_region、注册渠道 dim_channel、等级 level）；
-- 2）商品/类目/店铺：products, categories, shops；
-- 3）交易订单：orders, order_items（维度：店铺、渠道、地区、时间）；
-- 4）支付与退款：payments, refunds（用于转化率、退款率等指标）；
-- 5）营销：coupons, user_coupons, order_coupons（用于核算折扣、券效率、活动效果）；
-- 6）公共维度：dim_region, dim_channel；
-- 7）物流：logistics_providers, shipments, shipment_items, shipment_tracking_events（用于发货率、签收时效、承运商表现等分析）。
