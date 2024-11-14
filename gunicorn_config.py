# gunicorn_config.py

bind = "127.0.0.1:8000"
workers = 4
accesslog = "-"  # 将访问日志输出到标准输出
errorlog = "-"   # 将错误日志输出到标准输出
loglevel = "info"
