import os
import configparser
import time
import threading
import subprocess
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 设置日志
def setup_logging(log_file):
    if not os.path.exists(log_file):
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, 'w') as f:
            f.write('')  # 创建空日志文件

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            # logging.FileHandler(log_file),  # 输出到文件
            # logging.StreamHandler()         # 输出到控制台（可选）
        ]
    )

# 读取配置文件
def read_config(config_file, script_dir):
    config = configparser.ConfigParser()
    config.read(config_file)
    
    if 'Folders' not in config:
        logging.error("Configuration file is missing 'Folders' section.")
        return None
    
    folders = [line.strip() for line in config['Folders']['folders'].splitlines() if line.strip()]
    folders = [os.path.join(script_dir, 'data', folder) for folder in folders]
    
    # 过滤掉不存在的文件夹
    valid_folders = [folder for folder in folders if os.path.exists(folder)]
    
    return {
        'folders': valid_folders,
    }

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

def monitor_folders(config_file, script_dir, delay, indexer_script):
    config = read_config(config_file, script_dir)
    if config is None:
        return
    
    folders = config['folders']
    
    if not folders:
        logging.warning("No valid folders found. Exiting...")
        return

    event_handler = FileChangeHandler(delay, indexer_script)
    observer = Observer()
    for folder in folders:
        observer.schedule(event_handler, folder, recursive=True)
    observer.start()
    return observer

def reattempt_monitoring(config_file, script_dir, delay, indexer_script):
    while True:
        logging.info("Reattempting to monitor folders...")
        monitor_folders(config_file, script_dir, delay, indexer_script)
        time.sleep(60)  # 每60秒重新尝试一次

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, 'data', 'watcher.log')
    setup_logging(log_file)
    config_file = os.path.join(script_dir, 'data', 'config.ini')  # 更新配置文件路径
    delay_time = 30  # 30 seconds
    indexer_script = "indexer.py"
    logging.info("Starting file monitor...")
    reattempt_monitoring(config_file, script_dir, delay_time, indexer_script)
