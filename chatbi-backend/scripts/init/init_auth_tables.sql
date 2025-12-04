-- ============================================
-- ChatBI 系统数据库初始化
-- 
-- 使用方式：
-- mysql -u root -p < init_auth_tables.sql
--
-- Author: Agent
-- Time: 2025-12-03
-- ============================================

-- 创建系统数据库
CREATE DATABASE IF NOT EXISTS chatbi_sys
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE chatbi_sys;

-- 用户表
CREATE TABLE IF NOT EXISTS sys_users (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    nickname VARCHAR(100) DEFAULT '' COMMENT '昵称',
    is_root TINYINT(1) DEFAULT 0 COMMENT '是否为root用户 0-否 1-是',
    status TINYINT(1) DEFAULT 1 COMMENT '状态 0-禁用 1-启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_username (username),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

-- 登录日志表
CREATE TABLE IF NOT EXISTS sys_login_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '日志ID',
    user_id INT DEFAULT NULL COMMENT '用户ID',
    username VARCHAR(50) NOT NULL COMMENT '用户名',
    ip_address VARCHAR(50) DEFAULT '' COMMENT 'IP地址',
    location VARCHAR(255) DEFAULT '' COMMENT '登录地点',
    user_agent VARCHAR(500) DEFAULT '' COMMENT '浏览器UA',
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间',
    status TINYINT(1) DEFAULT 1 COMMENT '登录状态 0-失败 1-成功',
    message VARCHAR(255) DEFAULT '' COMMENT '备注信息',
    INDEX idx_user_id (user_id),
    INDEX idx_username (username),
    INDEX idx_login_time (login_time),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录日志表';

-- 初始化 root 用户
-- 默认密码: 123456
-- SHA256 哈希: 8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92
INSERT INTO sys_users (username, password_hash, nickname, is_root, status)
SELECT 'root', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '超级管理员', 1, 1
WHERE NOT EXISTS (SELECT 1 FROM sys_users WHERE username = 'root');
