# 使用官方 Python 3.9 slim 镜像作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 将项目文件复制到容器中
COPY . /app

# 安装依赖项
RUN pip install --no-cache-dir -r requirements.txt

# 检查并复制配置文件和索引目录
RUN if [ ! -f /app/data/config.ini ]; then cp /app/init/config.ini /app/data/; fi
RUN if [ ! -d /app/data/index_dir ]; then cp -r /app/init/index_dir /app/data/; fi
RUN if [ ! -d /app/data/input ]; then cp -r /app/init/input /app/data/; fi

# 运行一次 indexer.py
RUN bin/python indexer.py


# 设置定时任务
# RUN echo "*/5 * * * * /usr/local/bin/python /app/indexer.py" >> /etc/crontabs/root

# 暴露端口
EXPOSE 8000

CMD ["/app/entrypoint.sh"]
