import os
import logging
import configparser
import threading
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 自定义日志过滤器
class InotifyEventFilter(logging.Filter):
    def filter(self, record):
        # 过滤掉包含 "in-event" 的日志消息
        return "in-event" not in record.getMessage()

# 设置日志
def setup_logging(log_file):
    if not os.path.exists(log_file):
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, 'w') as f:
            f.write('')  # 创建空日志文件

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # 文件日志处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.addFilter(InotifyEventFilter())  # 添加过滤器
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    # 控制台日志处理器（可选）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.addFilter(InotifyEventFilter())  # 添加过滤器
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

# 读取配置文件
def read_config(config_file, script_dir):
    config = configparser.ConfigParser()
    config.read(config_file)
    
    if 'Folders' not in config:
        logging.error("Configuration file is missing 'Folders' section.")
        return None
    
    folders = [line.strip() for line in config['Folders']['folders'].splitlines() if line.strip()]
    folders = [os.path.join(script_dir, 'data', folder) for folder in folders]
    
    # 过滤掉不存在的文件夹并记录警告
    valid_folders = []
    for folder in folders:
        if os.path.exists(folder):
            valid_folders.append(folder)
        else:
            logging.warning(f"{folder} 文件夹不存在")
    
    return valid_folders

# 文件变更处理类
class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, delay, indexer_script):
        self.delay = delay
        self.indexer_script = indexer_script
        self.timer = None
        self.indexing = False

    def on_any_event(self, event):
        if self.indexing:
            return
        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(self.delay, self.start_indexer)
        self.timer.start()

    def start_indexer(self):
        self.indexing = True
        logging.info(f"Starting {self.indexer_script}...")
        subprocess.run(["python", self.indexer_script])
        self.indexing = False

# 监控文件夹
def monitor_folders(config_file, script_dir, delay, indexer_script):
    folders = read_config(config_file, script_dir)
    if not folders:
        logging.warning("No valid folders found. Exiting...")
        return None

    event_handler = FileChangeHandler(delay, indexer_script)
    observer = Observer()
    for folder in folders:
        observer.schedule(event_handler, folder, recursive=True)
    observer.start()
    return observer

# 主函数
def main():
    global observer
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, 'data', 'watcher.log')
    setup_logging(log_file)
    
    config_file = os.path.join(script_dir, 'data', 'config.ini')
    indexer_script = os.path.join(script_dir, 'indexer.py')
    delay = 30  # 30秒延迟
    
    observer = monitor_folders(config_file, script_dir, delay, indexer_script)
    if not observer:
        return

    # 每隔60秒重新读取配置文件
    def reload_config():
        global observer
        while True:
            logging.info("Reloading configuration...")
            new_folders = read_config(config_file, script_dir)
            if new_folders:
                # 停止当前的监控
                observer.stop()
                observer.join()
                # 重新启动监控
                observer = monitor_folders(config_file, script_dir, delay, indexer_script)
                if not observer:
                    logging.warning("Failed to reload configuration. Exiting...")
                    return
            threading.Event().wait(60)

    config_reload_thread = threading.Thread(target=reload_config)
    config_reload_thread.daemon = True
    config_reload_thread.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
