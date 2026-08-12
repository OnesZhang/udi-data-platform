#!/usr/bin/env python3
"""数据库初始化模块 - 创建数据库与表结构"""

import logging
import os

import mysql.connector

logger = logging.getLogger(__name__)


def initialize_database(config) -> bool:
    """创建数据库（如不存在）并初始化表结构。"""
    try:
        conn = mysql.connector.connect(
            host=config.db_host,
            port=config.db_port,
            user=config.db_user,
            password=config.db_password,
            connection_timeout=15,
        )
    except mysql.connector.Error as e:
        logger.error(f"数据库连接失败: {e}")
        return False

    try:
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{config.db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.execute(f"USE `{config.db_name}`")

        cursor.execute("SHOW TABLES LIKE 'udi_devices'")
        if cursor.fetchone():
            logger.info("数据表已存在，跳过建表")
            return True

        sql_path = os.path.join(os.path.dirname(__file__), "init_db_complete.sql")
        with open(sql_path, encoding="utf-8") as f:
            statements = [s.strip() for s in f.read().split(";") if s.strip()]
        for statement in statements:
            cursor.execute(statement)
        conn.commit()
        logger.info("数据库初始化完成")
        return True

    except mysql.connector.Error as e:
        logger.error(f"数据库初始化失败: {e}")
        return False
    finally:
        conn.close()
