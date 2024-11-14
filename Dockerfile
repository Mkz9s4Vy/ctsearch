# 使用官方 Python 3.9 slim 镜像作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 将项目文件复制到容器中
COPY . /app

# 安装依赖项
RUN pip install --no-cache-dir -r requirements.txt

# 运行一次 indexer.py
RUN python indexer.py

# 设置定时任务
# RUN echo "*/5 * * * * /usr/local/bin/python /app/indexer.py" >> /etc/crontabs/root

# 启动 Gunicorn
CMD ["gunicorn", "--workers=4", "--bind=0.0.0.0:8000", "--config", "gunicorn_config.py", "wsgi:app"]

# 将 data 目录映射到主机
VOLUME /app/data

# 暴露端口
EXPOSE 8000
