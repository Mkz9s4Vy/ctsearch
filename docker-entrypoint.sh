#!/bin/sh

# 创建必要的目录并设置权限
if [ ! -d /app/data/config ]; then mkdir -p /app/data/config; fi
if [ ! -d /app/data/logs ]; then mkdir -p /app/data/logs; fi
if [ ! -d /app/data/singlefile ]; then mkdir -p /app/data/singlefile; fi


# 复制初始化文件和目录
if [ ! -d /app/data/index_dir ]; then cp -r /app/init/index_dir /app/data/; fi
if [ ! -f /app/data/config/config.ini ]; then cp /app/init/config/config.ini /app/data/config/; fi
if [ ! -f /app/data/config/webdav_config.yaml ]; then cp /app/init/config/webdav_config.yaml /app/data/config/; fi

# 所有目录和文件都应该属于 appuser:appgroup
chown -R 1000:1000 /app/data


supervisord -c supervisord.conf

