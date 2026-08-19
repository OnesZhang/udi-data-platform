#!/usr/bin/env python3
"""Create or reset the configured MySQL database."""

import logging
from pathlib import Path

import mysql.connector

logger = logging.getLogger(__name__)


def _connect_server(config):
    return mysql.connector.connect(
        host=config.db_host,
        port=config.db_port,
        user=config.db_user,
        password=config.db_password,
        connection_timeout=30,
    )


def _schema_statements() -> list:
    path = Path(__file__).with_name("init_db_complete.sql")
    return [
        statement.strip()
        for statement in path.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]


def initialize_database(config) -> bool:
    try:
        conn = _connect_server(config)
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{config.db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(f"USE `{config.db_name}`")
            for statement in _schema_statements():
                cursor.execute(statement)
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        logger.info("数据库结构已就绪: %s", config.db_name)
        return True
    except mysql.connector.Error as error:
        logger.error("数据库初始化失败: %s", error)
        return False


def reset_database(config) -> bool:
    """Drop the configured database; this is intentionally an explicit test-only action."""
    try:
        conn = _connect_server(config)
        cursor = conn.cursor()
        try:
            cursor.execute(f"DROP DATABASE IF EXISTS `{config.db_name}`")
            conn.commit()
        finally:
            cursor.close()
            conn.close()
        logger.warning("数据库已删除，下一步会重新创建: %s", config.db_name)
        return True
    except mysql.connector.Error as error:
        logger.error("数据库重置失败: %s", error)
        return False
