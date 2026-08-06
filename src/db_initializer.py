#!/usr/bin/env python3
"""
数据库初始化模块 - 自动创建表结构
"""

import mysql.connector
import logging
import os

logger = logging.getLogger(__name__)

class DatabaseInitializer:
    """数据库初始化器"""
    
    def __init__(self, config):
        """
        初始化
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.connection = None
    
    def connect(self):
        """连接数据库"""
        try:
            # 先连接MySQL服务器（不指定数据库）
            self.connection = mysql.connector.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                user=self.config.db_user,
                password=self.config.db_password
            )
            logger.info("MySQL服务器连接成功")
            return True
        except mysql.connector.Error as e:
            logger.error(f"MySQL服务器连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
    
    def create_database(self):
        """创建数据库"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.config.db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            logger.info(f"数据库 {self.config.db_name} 创建/验证成功")
            cursor.close()
            return True
        except mysql.connector.Error as e:
            logger.error(f"创建数据库失败: {e}")
            return False
    
    def switch_database(self):
        """切换到目标数据库"""
        try:
            self.connection.database = self.config.db_name
            logger.info(f"已切换到数据库: {self.config.db_name}")
            return True
        except mysql.connector.Error as e:
            logger.error(f"切换数据库失败: {e}")
            return False
    
    def execute_sql_file(self, sql_file_path):
        """执行SQL文件"""
        try:
            if not os.path.exists(sql_file_path):
                logger.error(f"SQL文件不存在: {sql_file_path}")
                return False
            
            with open(sql_file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            cursor = self.connection.cursor()
            
            # 分割SQL语句
            sql_statements = sql_content.split(';')
            
            executed_count = 0
            for statement in sql_statements:
                statement = statement.strip()
                if statement and not statement.startswith('--'):
                    try:
                        cursor.execute(statement)
                        executed_count += 1
                    except mysql.connector.Error as e:
                        # 忽略"已存在"的错误
                        if "already exists" not in str(e).lower():
                            logger.warning(f"执行SQL语句时出错: {e}")
                            logger.warning(f"SQL: {statement[:100]}...")
            
            self.connection.commit()
            cursor.close()
            
            logger.info(f"SQL文件执行完成，执行了 {executed_count} 条语句")
            return True
            
        except Exception as e:
            logger.error(f"执行SQL文件失败: {e}")
            return False
    
    def check_tables_exist(self):
        """检查表是否存在"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SHOW TABLES LIKE 'udi_devices'")
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                logger.info("udi_devices 表已存在")
                return True
            else:
                logger.info("udi_devices 表不存在，需要创建")
                return False
                
        except mysql.connector.Error as e:
            logger.error(f"检查表是否存在失败: {e}")
            return False
    
    def initialize(self):
        """
        完整的初始化流程
        
        Returns:
            是否初始化成功
        """
        logger.info("=" * 60)
        logger.info("开始数据库初始化")
        logger.info("=" * 60)
        
        # 1. 连接MySQL服务器
        if not self.connect():
            return False
        
        try:
            # 2. 创建数据库
            if not self.create_database():
                return False
            
            # 3. 切换到目标数据库
            if not self.switch_database():
                return False
            
            # 4. 检查表是否存在
            if self.check_tables_exist():
                logger.info("数据库表已存在，跳过创建")
                return True
            
            # 5. 执行SQL初始化脚本
            sql_file_path = os.path.join(os.path.dirname(__file__), 'init_db_complete.sql')
            if not self.execute_sql_file(sql_file_path):
                return False
            
            logger.info("=" * 60)
            logger.info("数据库初始化完成")
            logger.info("=" * 60)
            
            return True
            
        finally:
            self.disconnect()
