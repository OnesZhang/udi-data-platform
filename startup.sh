#!/bin/bash
echo "========================================"
echo "UDI医疗器械数据平台启动"
echo "========================================"

# 检查环境变量
echo "检查数据库配置..."
if [ -z "$DB_HOST" ]; then
    echo "错误: DB_HOST 未设置"
    exit 1
fi

echo "数据库主机: $DB_HOST"
echo "数据库端口: $DB_PORT"
echo "数据库名称: $DB_NAME"

# 创建必要目录
mkdir -p /app/inbox

# 运行Python应用（长期运行）
echo "启动应用（定时任务模式）..."
exec python app.py
