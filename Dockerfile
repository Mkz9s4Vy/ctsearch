# 使用基础镜像
FROM python:3-alpine

# 设置工作目录
WORKDIR /app

# 复制应用程序文件
COPY . /app

# 安装依赖
RUN pip install --no-cache -r requirements.txt

# 创建一个与容器外用户 UID 和 GID 相同的用户
RUN addgroup -g 1000 appgroup && \
    adduser -D -u 1000 -G appgroup appuser

# 切换到新创建的用户
USER appuser

# 暴露端口
EXPOSE 8000

# 设置 ENTRYPOINT
ENTRYPOINT ["sh", "-c"]

# 在容器启动时执行文件检查和复制操作，然后运行 indexer.py，最后运行 supervisord
CMD ["if [ ! -d /app/data/config ]; then mkdir -p /app/data/config; fi && \
    if [ ! -d /app/data/logs ]; then mkdir -p /app/data/logs; fi && \
    if [ ! -d /app/data/singlefile ]; then mkdir -p /app/data/singlefile; fi && \
    if [ ! -f /app/data/config/config.ini ]; then cp /app/init/config/config.ini /app/data/config/; fi && \
    if [ ! -f /app/data/config/webdav_config.yaml ]; then cp /app/init/config/webdav_config.yaml /app/data/config/; fi && \
    if [ ! -d /app/data/index_dir ]; then cp -r /app/init/index_dir /app/data/; fi && \
    if [ ! -d /app/data/input ]; then cp -r /app/init/input /app/data/; fi && \
    supervisord -c supervisord.conf"]
