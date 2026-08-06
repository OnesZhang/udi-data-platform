#!/usr/bin/env python3
"""
UDI医疗器械数据平台 - 主应用入口

特点：
- Docker容器长期运行
- 每日定时自动检查RSS并下载
- 下载后自动处理inbox目录
- 支持手动上传文件
"""

import sys
import os
import logging
import time
import signal
from datetime import datetime, timedelta
from config import Config
from db_initializer import DatabaseInitializer
from downloader import UdiDownloader
from parser_complete import UdiParserComplete
from importer import UdiImporter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局停止标志
shutdown_flag = False

def signal_handler(signum, frame):
    """信号处理函数，用于优雅关闭"""
    global shutdown_flag
    logger.info("收到停止信号，正在关闭...")
    shutdown_flag = True

def initialize_database(config):
    """初始化数据库"""
    logger.info("=" * 60)
    logger.info("初始化数据库")
    logger.info("=" * 60)
    
    initializer = DatabaseInitializer(config)
    return initializer.initialize()

def test_database_connection(config):
    """测试数据库连接"""
    logger.info("=" * 60)
    logger.info("测试数据库连接")
    logger.info("=" * 60)
    
    importer = UdiImporter(config)
    if importer.test_connection():
        logger.info("数据库连接测试通过")
        return True
    else:
        logger.error("数据库连接测试失败")
        return False

def download_latest_file(config):
    """下载最新文件到inbox目录"""
    logger.info("=" * 60)
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 检查并下载最新文件")
    logger.info("=" * 60)
    
    downloader = UdiDownloader(config)
    filepath = downloader.download_latest_daily()
    
    if filepath:
        logger.info(f"下载成功: {filepath}")
        return True
    else:
        logger.info("没有新文件或下载失败")
        return False

def process_inbox_files(config):
    """处理inbox目录下的所有ZIP文件"""
    logger.info("=" * 60)
    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 扫描并处理inbox文件")
    logger.info("=" * 60)
    
    # 获取inbox目录下的所有ZIP文件
    downloader = UdiDownloader(config)
    files = downloader.list_inbox_files()
    
    if not files:
        logger.info("inbox目录中没有ZIP文件")
        return {'status': 'no_files', 'processed': 0}
    
    logger.info(f"找到 {len(files)} 个ZIP文件")
    
    # 初始化解析器和导入器
    parser = UdiParserComplete()
    importer = UdiImporter(config)
    
    total_processed = 0
    total_success = 0
    total_failed = 0
    
    # 逐个处理文件
    for file_info in files:
        zip_path = file_info['path']
        filename = file_info['filename']
        
        logger.info(f"处理文件: {filename}")
        
        try:
            # 解析ZIP文件并导入数据
            record_generator = parser.parse_zip_file(zip_path)
            result = importer.import_from_generator(record_generator)
            
            if result['status'] == 'completed':
                logger.info(f"✅ 处理完成: {filename} ({result['total_records']}条)")
                total_success += 1
            else:
                logger.error(f"❌ 处理失败: {filename}")
                total_failed += 1
            
            total_processed += 1
            
        except Exception as e:
            logger.error(f"❌ 处理异常: {filename} - {e}")
            total_failed += 1
            total_processed += 1
    
    logger.info(f"处理汇总: 总计{total_processed}, 成功{total_success}, 失败{total_failed}")
    
    return {
        'status': 'completed',
        'total': total_processed,
        'success': total_success,
        'failed': total_failed
    }

def run_scheduled_task(config, task_func, interval_hours=24):
    """
    定时执行任务
    
    Args:
        config: 配置对象
        task_func: 任务函数
        interval_hours: 执行间隔（小时）
    """
    global shutdown_flag
    
    logger.info(f"定时任务启动，间隔: {interval_hours}小时")
    
    while not shutdown_flag:
        try:
            # 执行任务
            task_func(config)
            
            # 等待下一次执行
            next_run = datetime.now() + timedelta(hours=interval_hours)
            logger.info(f"下次执行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 分段等待，以便响应停止信号
            wait_seconds = interval_hours * 3600
            waited = 0
            while waited < wait_seconds and not shutdown_flag:
                time.sleep(min(60, wait_seconds - waited))
                waited += 60
                
        except Exception as e:
            logger.error(f"定时任务执行异常: {e}")
            # 出错后等待1分钟再重试
            time.sleep(60)

def main():
    """主函数"""
    global shutdown_flag
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 60)
    logger.info("UDI医疗器械数据平台启动")
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    try:
        # 1. 加载配置
        config = Config()
        
        # 2. 初始化数据库
        if not initialize_database(config):
            logger.error("数据库初始化失败，系统无法启动")
            sys.exit(1)
        
        # 3. 测试数据库连接
        if not test_database_connection(config):
            logger.error("数据库连接测试失败，系统无法启动")
            sys.exit(1)
        
        # 4. 启动时先处理一次
        logger.info("启动时执行首次处理...")
        download_latest_file(config)
        process_inbox_files(config)
        
        # 5. 进入定时循环
        logger.info("=" * 60)
        logger.info("进入定时任务模式，每24小时检查一次")
        logger.info("按 Ctrl+C 停止服务")
        logger.info("=" * 60)
        
        def daily_task(cfg):
            """每日任务：下载+处理"""
            download_latest_file(cfg)
            process_inbox_files(cfg)
        
        run_scheduled_task(config, daily_task, interval_hours=24)
        
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"系统启动失败: {e}")
        sys.exit(1)
    finally:
        logger.info("系统已停止")

if __name__ == "__main__":
    main()
