FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY src/requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY src/ .

# 创建数据目录
RUN mkdir -p /app/inbox

# 复制启动脚本
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

# 运行启动脚本
CMD ["/startup.sh"]
