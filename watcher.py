import os
import logging
import configparser
import threading
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 设置日志记录
def setup_logging(log_file):
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler(log_file),
                            logging.StreamHandler()
                        ])

# 读取配置文件
def read_config(config_file, script_dir):
    config = configparser.ConfigParser()
    config.read(config_file)
    
    if 'Folders' not in config:
        logging.error("Configuration file is missing 'Folders' section.")
        return None
    
    folders = [folder.strip() for folder in config['Folders']['folders'].split(',') if folder.strip()]
    folders = [os.path.join(script_dir, 'data', folder) for folder in folders]
    
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

    def start_indexer_for_new_folders(self, new_folders):
        self.indexing = True
        logging.info(f"Starting {self.indexer_script} for new folders...")
        subprocess.run(["python", self.indexer_script])
        self.indexing = False

# 监控文件夹
def monitor_folders(delay, indexer_script, current_folders):
    if not current_folders:
        logging.warning("No valid folders found. Exiting...")
        return None
    
    event_handler = FileChangeHandler(delay, indexer_script)
    observer = Observer()
    for folder in current_folders:
        observer.schedule(event_handler, folder, recursive=True)
    observer.start()
    return observer

# 主函数
def main():
    global observer, current_folders
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, 'data', 'watcher.log')
    setup_logging(log_file)
    
    config_file = os.path.join(script_dir, 'data', 'config.ini')
    indexer_script = os.path.join(script_dir, 'indexer.py')
    delay = 30  # 30秒延迟
    
    # 初始化现文件夹列表
    current_folders = read_config(config_file, script_dir)
    if not current_folders:
        logging.warning("No valid folders found. Exiting...")
        return
    
    # 触发初次索引
    event_handler = FileChangeHandler(delay, indexer_script)
    event_handler.start_indexer_for_new_folders(current_folders)

    observer = monitor_folders(delay, indexer_script, current_folders)
    if not observer:
        return

    # 每隔60秒重新读取配置文件
    def reload_config():
        global observer, current_folders
        while True:
            logging.info("Reloading configuration...")
            new_folders = read_config(config_file, script_dir)
            if new_folders:
                # 对比新旧文件夹列表
                added_folders = [folder for folder in new_folders if folder not in current_folders]
                if added_folders:
                    logging.info(f"New folders added: {added_folders}")
                    # 停止当前的监控
                    observer.stop()
                    observer.join()
                    # 更新现文件夹列表
                    current_folders = new_folders
                    # 触发初次索引
                    event_handler = FileChangeHandler(delay, indexer_script)
                    event_handler.start_indexer_for_new_folders(current_folders)
                    # 重新启动监控
                    observer = monitor_folders(delay, indexer_script, current_folders)
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
