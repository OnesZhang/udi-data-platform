#!/usr/bin/env python3
"""
RSS订阅下载模块 - 自动下载UDI数据到inbox目录
"""

import requests
import feedparser
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class UdiDownloader:
    """UDI数据下载器"""
    
    def __init__(self, config):
        """
        初始化下载器
        
        Args:
            config: 配置对象
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 确保inbox目录存在
        os.makedirs(config.inbox_dir, exist_ok=True)
    
    def fetch_rss(self, rss_url: str) -> Optional[Dict[str, Any]]:
        """
        获取RSS内容
        
        Args:
            rss_url: RSS URL
            
        Returns:
            RSS解析结果
        """
        try:
            logger.info(f"获取RSS: {rss_url}")
            response = self.session.get(rss_url, timeout=30)
            response.raise_for_status()
            
            # 解析RSS
            feed = feedparser.parse(response.content)
            
            if feed.entries:
                logger.info(f"获取到 {len(feed.entries)} 个条目")
                return feed
            else:
                logger.warning("RSS中没有找到条目")
                return None
                
        except Exception as e:
            logger.error(f"获取RSS失败: {e}")
            return None
    
    def get_latest_file_info(self, rss_url: str) -> Optional[Dict[str, str]]:
        """
        从RSS中获取最新文件信息
        
        Args:
            rss_url: RSS URL
            
        Returns:
            文件信息字典 {title, link, description}
        """
        feed = self.fetch_rss(rss_url)
        if not feed or not feed.entries:
            return None
        
        # 获取第一个条目（最新的）
        entry = feed.entries[0]
        file_info = {
            'title': entry.get('title', ''),
            'link': entry.get('link', ''),
            'description': entry.get('description', '')
        }
        
        logger.info(f"最新文件: {file_info['title']}")
        logger.info(f"描述: {file_info['description']}")
        
        return file_info
    
    def download_file(self, url: str, filename: str) -> Optional[str]:
        """
        下载文件到inbox目录
        
        Args:
            url: 下载链接
            filename: 文件名
            
        Returns:
            下载后的文件路径
        """
        try:
            # 完整文件路径（inbox目录下）
            filepath = os.path.join(self.config.inbox_dir, filename)
            
            # 检查文件是否已存在
            if os.path.exists(filepath):
                logger.info(f"文件已存在，跳过下载: {filepath}")
                return filepath
            
            logger.info(f"开始下载: {url}")
            logger.info(f"保存到: {filepath}")
            
            response = self.session.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0
            
            # 写入文件
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # 进度显示（每10MB显示一次）
                        if total_size > 0 and downloaded_size % (10 * 1024 * 1024) == 0:
                            progress = (downloaded_size / total_size) * 100
                            logger.info(f"下载进度: {progress:.1f}% ({downloaded_size / 1024 / 1024:.1f}MB)")
            
            logger.info(f"下载完成: {filepath} ({downloaded_size / 1024 / 1024:.1f}MB)")
            return filepath
            
        except Exception as e:
            logger.error(f"下载失败: {e}")
            # 删除可能不完整的文件
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
    
    def download_latest_daily(self) -> Optional[str]:
        """
        下载最新的每日文件到inbox目录
        
        Returns:
            下载后的文件路径
        """
        logger.info("=" * 60)
        logger.info("开始下载最新每日文件")
        logger.info("=" * 60)
        
        # 获取文件信息
        file_info = self.get_latest_file_info(self.config.rss_daily_url)
        if not file_info or not file_info['link']:
            logger.error("无法获取每日文件下载链接")
            return None
        
        # 使用RSS中的文件名，如果没有则生成
        filename = file_info['title']
        if not filename or not filename.endswith('.zip'):
            filename = f"UDID_DAILY_{datetime.now().strftime('%Y%m%d')}.zip"
        
        # 下载文件
        return self.download_file(file_info['link'], filename)
    
    def download_latest_weekly(self) -> Optional[str]:
        """
        下载最新的每周文件到inbox目录
        
        Returns:
            下载后的文件路径
        """
        logger.info("=" * 60)
        logger.info("开始下载最新每周文件")
        logger.info("=" * 60)
        
        file_info = self.get_latest_file_info(self.config.rss_weekly_url)
        if not file_info or not file_info['link']:
            logger.error("无法获取每周文件下载链接")
            return None
        
        filename = file_info['title']
        if not filename or not filename.endswith('.zip'):
            filename = f"UDID_WEEKLY_{datetime.now().strftime('%Y%m%d')}.zip"
        
        return self.download_file(file_info['link'], filename)
    
    def download_latest_monthly(self) -> Optional[str]:
        """
        下载最新的每月文件到inbox目录
        
        Returns:
            下载后的文件路径
        """
        logger.info("=" * 60)
        logger.info("开始下载最新每月文件")
        logger.info("=" * 60)
        
        file_info = self.get_latest_file_info(self.config.rss_monthly_url)
        if not file_info or not file_info['link']:
            logger.error("无法获取每月文件下载链接")
            return None
        
        filename = file_info['title']
        if not filename or not filename.endswith('.zip'):
            filename = f"UDID_MONTHLY_{datetime.now().strftime('%Y%m%d')}.zip"
        
        return self.download_file(file_info['link'], filename)
    
    def download_latest_full(self) -> Optional[str]:
        """
        下载最新的全量文件到inbox目录
        
        Returns:
            下载后的文件路径
        """
        logger.info("=" * 60)
        logger.info("开始下载最新全量文件")
        logger.info("=" * 60)
        
        file_info = self.get_latest_file_info(self.config.rss_full_url)
        if not file_info or not file_info['link']:
            logger.error("无法获取全量文件下载链接")
            return None
        
        filename = file_info['title']
        if not filename or not filename.endswith('.zip'):
            filename = f"UDID_FULL_{datetime.now().strftime('%Y%m%d')}.zip"
        
        return self.download_file(file_info['link'], filename)
    
    def download_latest(self, file_type: str = 'daily') -> Optional[str]:
        """
        根据类型下载最新文件到inbox目录
        
        Args:
            file_type: 文件类型 (daily, weekly, monthly, full)
            
        Returns:
            下载后的文件路径
        """
        download_methods = {
            'daily': self.download_latest_daily,
            'weekly': self.download_latest_weekly,
            'monthly': self.download_latest_monthly,
            'full': self.download_latest_full
        }
        
        method = download_methods.get(file_type)
        if not method:
            logger.error(f"不支持的文件类型: {file_type}")
            return None
        
        return method()
    
    def list_inbox_files(self) -> list:
        """
        列出inbox目录中的所有ZIP文件
        
        Returns:
            ZIP文件列表
        """
        files = []
        if os.path.exists(self.config.inbox_dir):
            for f in os.listdir(self.config.inbox_dir):
                if f.endswith('.zip'):
                    filepath = os.path.join(self.config.inbox_dir, f)
                    files.append({
                        'filename': f,
                        'path': filepath,
                        'size': os.path.getsize(filepath)
                    })
        
        # 按文件名排序（日期）
        files.sort(key=lambda x: x['filename'], reverse=True)
        
        return files
