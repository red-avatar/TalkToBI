-- ============================================================
-- 电商示例库 - 删除所有表（按外键依赖顺序）
-- 执行前请确认！此操作不可逆！
-- ============================================================

USE chatbi;

-- 禁用外键检查（加速删除）
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 第一层：无依赖或仅被依赖的基础表（最后删除）
-- ============================================================

-- 物流轨迹事件（依赖 shipments）
DROP TABLE IF EXISTS shipment_tracking_events;

-- 发货明细（依赖 shipments, order_items）
DROP TABLE IF EXISTS shipment_items;

-- 发货单（依赖 orders, logistics_providers）
DROP TABLE IF EXISTS shipments;

-- 物流承运商（被 shipments 依赖）
DROP TABLE IF EXISTS logistics_providers;

-- ============================================================
-- 第二层：优惠券相关
-- ============================================================

-- 订单用券（依赖 orders, coupons）
DROP TABLE IF EXISTS order_coupons;

-- 用户领券（依赖 users, coupons）
DROP TABLE IF EXISTS user_coupons;

-- 优惠券（依赖 shops）
DROP TABLE IF EXISTS coupons;

-- ============================================================
-- 第三层：支付退款相关
-- ============================================================

-- 退款（依赖 orders, payments）
DROP TABLE IF EXISTS refunds;

-- 支付（依赖 orders）
DROP TABLE IF EXISTS payments;

-- ============================================================
-- 第四层：订单相关
-- ============================================================

-- 订单明细（依赖 orders, products）
DROP TABLE IF EXISTS order_items;

-- 订单（依赖 users, shops, dim_channel, dim_region）
DROP TABLE IF EXISTS orders;

-- ============================================================
-- 第五层：商品相关
-- ============================================================

-- 商品（依赖 categories, shops）
DROP TABLE IF EXISTS products;

-- 类目（自引用）
DROP TABLE IF EXISTS categories;

-- ============================================================
-- 第六层：店铺和用户
-- ============================================================

-- 店铺（依赖 users, dim_region）
DROP TABLE IF EXISTS shops;

-- 用户（依赖 dim_region, dim_channel）
DROP TABLE IF EXISTS users;

-- ============================================================
-- 第七层：维度表（最基础的表）
-- ============================================================

-- 渠道维度
DROP TABLE IF EXISTS dim_channel;

-- 地区维度
DROP TABLE IF EXISTS dim_region;

-- ============================================================
-- 恢复外键检查
-- ============================================================
SET FOREIGN_KEY_CHECKS = 1;

-- 完成提示
SELECT '所有表已删除！' AS message;
