import os
import os.path
import sqlite3
import configparser
import queue
import time
import logging
from logging.handlers import RotatingFileHandler
import multiprocessing
import shutil
from concurrent.futures import ProcessPoolExecutor
from bs4 import BeautifulSoup
import markdown
import jieba.analyse
from jieba.analyse import ChineseAnalyzer
from whoosh.fields import Schema, TEXT, ID
from whoosh.index import create_in, open_dir, exists_in, create_in



# 读取配置文件
def read_config(config_file, script_dir):
    config = configparser.ConfigParser()
    config.read(config_file)
    folders = [line.strip() for line in config['Folders']['folders'].splitlines() if line.strip()]
    folders = [os.path.join(script_dir, 'data', folder) for folder in folders]
    return {
        'folders': folders,
        'max_scan_processes': int(config['Scan_processes']['max_scan_processes']),
        'max_files_per_batch': int(config['Batch']['max_files_per_batch']),
        'queue_size_limit': int(config['Queue']['queue_size_limit']),
        'log_level': config['Logging']['log_level'],
        'max_index_processes': int(config['Index_processes']['max_index_processes'])
    }


# 创建数据库和表
def create_database_if_not_exists(db_path):
    if not os.path.exists(db_path):
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE chkchng (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    file_name TEXT,
                    extension TEXT,
                    file_type TEXT,
                    creation_time TEXT,
                    modification_time TEXT,
                    file_size INTEGER,
                    is_hidden INTEGER,
                    status TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE indexed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT,
                    file_name TEXT,
                    extension TEXT,
                    file_type TEXT,
                    creation_time TEXT,
                    modification_time TEXT,
                    file_size INTEGER,
                    is_hidden INTEGER,
                    status TEXT,
                    file_content TEXT
                )
            ''')
            conn.commit()

# 获取文件属性
def get_file_attributes(file_path):
    try:
        file_stats = os.stat(file_path)
        return {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'extension': os.path.splitext(file_path)[1],
            'file_type': 'file' if os.path.isfile(file_path) else 'directory',
            'creation_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stats.st_ctime)),
            'modification_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(file_stats.st_mtime)),
            'file_size': file_stats.st_size,
            'is_hidden': int(os.path.basename(file_path).startswith('.')),
            'status': 'chkchng'
        }
    except Exception as e:
        logging.error(f"Error getting file attributes for {file_path}: {e}")
        return None

# 扫描文件夹
def scan_folder(folder_path, file_queue):
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_attributes = get_file_attributes(file_path)
            if file_attributes:
                file_queue.put(file_attributes)


# 写入数据库
def insert_file_attributes_to_db(conn, attributes):
    cursor = conn.cursor()
    for attr in attributes:
        try:
            cursor.execute('''
                INSERT INTO chkchng (file_path, file_name, extension, file_type, creation_time, modification_time, file_size, is_hidden, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (attr['file_path'], attr['file_name'], attr['extension'], attr['file_type'], attr['creation_time'], attr['modification_time'], attr['file_size'], attr['is_hidden'], attr['status']))
        except Exception as e:
            logging.error(f"Error inserting file attributes into database: {e}")
    conn.commit()

# 对比和更新数据库
def compare_and_update_db(conn):
    cursor = conn.cursor()

    # 获取chkchng表和indexed表的数据
    cursor.execute("SELECT file_path, modification_time FROM chkchng")
    chkchng_data = cursor.fetchall()
    cursor.execute("SELECT file_path, modification_time FROM indexed")
    indexed_data = cursor.fetchall()

    chkchng_dict = {item[0]: item[1] for item in chkchng_data}
    indexed_dict = {item[0]: item[1] for item in indexed_data}

    # 删除indexed表中不存在于chkchng表的数据
    # 数据存在于 indexed 表，而不存在于 chkchng 表
    for file_path in indexed_dict:
        if file_path not in chkchng_dict:
            cursor.execute("DELETE FROM indexed WHERE file_path=?", (file_path,))
            logging.info(f"Removed files from indexed table {file_path}.")

    # 对比数据并更新indexed表
    for file_path, chkchng_mod_time in chkchng_dict.items():
        if file_path not in indexed_dict:
        # 数据存在于 chkchng 表，而不存在于 indexed 表
            cursor.execute("INSERT INTO indexed SELECT *, NULL FROM chkchng WHERE file_path=?", (file_path,))
            logging.info(f"Added files to indexed table {file_path}.")
        else:
        # 数据存在于 chkchng 表，也存在于 indexed 表
            indexed_mod_time = indexed_dict[file_path]
            # chkchng表中的modification_time 和 indexed 表中的 modification_time 相同，表示两个文件相同，则不需要做任何事
            if chkchng_mod_time == indexed_mod_time:
                logging.debug(f"Skipped as modification times are the same {file_path}.")
            else:
                # 其他所有情况，删除 indexed 表中的数据，复制 chkchng 表中的数据到 Indexed 表
                cursor.execute("DELETE FROM indexed WHERE file_path=?", (file_path,))
                cursor.execute("INSERT INTO indexed SELECT *, NULL FROM chkchng WHERE file_path=?", (file_path,))
                logging.info(f"Updated files in indexed table {file_path}.")

    # 清空chkchng表
    cursor.execute("DELETE FROM chkchng")
    logging.debug("Cleared chkchng table.")

    conn.commit()

# 解析Markdown文件
def parse_md(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            return markdown.markdown(content)
    except Exception as e:
        logging.error(f"Error parsing Markdown file {file_path}: {e}")
        return None

# 解析HTML文件
def parse_html(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            soup = BeautifulSoup(content, 'html.parser')
            return soup.get_text()
    except Exception as e:
        logging.error(f"Error parsing HTML file {file_path}: {e}")
        return None

# 解析文件
def parse_file(file_path, extension):
    if extension == '.md':
        return parse_md(file_path)
    elif extension == '.html':
        return parse_html(file_path)
    else:
        raise ValueError(f"Unsupported file extension: {extension}")

def index_file_content(file_path, file_name, file_content, writer):
    # 使用结巴分词进行分词索引
    segmented_content = " ".join(jieba.cut_for_search(file_content, HMM=True))
    writer.add_document(file_name=file_name, file_path=file_path, file_content=segmented_content)

# 设置日志格式
def setup_logging(log_file_path, log_level):
    logger = logging.getLogger()
    logger.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = RotatingFileHandler(log_file_path, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# 主函数
def main():

    # 指定目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "data/config.ini")
    db_file_path = os.path.join(script_dir, "data/index.db")
    log_file_path = os.path.join(script_dir, "data/logs.log")

    # 检查日志文件是否存在，如果不存在则创建
    if not os.path.exists(log_file_path):
        with open(log_file_path, 'a'):
            os.utime(log_file_path, None)

    config = read_config(config_path, script_dir)
    create_database_if_not_exists(db_file_path)
    # 配置日志输出到文件
    setup_logging(log_file_path, config['log_level'])
    
    # 使用 multiprocessing.Manager 创建队列
    manager = multiprocessing.Manager()
    file_queue = manager.Queue(maxsize=config['queue_size_limit'])
    
    with sqlite3.connect(db_file_path) as conn:
        def process_queue():
            batch = []
            while not file_queue.empty() and len(batch) < config['max_files_per_batch']:
                try:
                    batch.append(file_queue.get(timeout=1))
                except queue.Empty:
                    break
            if batch:
                insert_file_attributes_to_db(conn, batch)

        def scan_folders():
            with ProcessPoolExecutor(max_workers=config['max_scan_processes']) as executor:
                for folder in config['folders']:
                    executor.submit(scan_folder, folder, file_queue)

        # 启动文件夹扫描和队列处理
        scan_folders()
        process_queue()
        compare_and_update_db(conn)

        # 解析文件并更新数据库
        cursor = conn.cursor()
        cursor.execute("SELECT file_path, extension FROM indexed WHERE file_content IS NULL")
        files_to_parse = cursor.fetchall()

        with ProcessPoolExecutor(max_workers=config['max_index_processes']) as executor:
            for file_path, extension in files_to_parse:
                future = executor.submit(parse_file, file_path, extension)
                content = future.result()
                if content:
                    cursor.execute("UPDATE indexed SET file_content=? WHERE file_path=?", (content, file_path))
                    logging.info(f"Parsed and updated file content {file_path}.")

        conn.commit()


        # 创建 Whoosh schema
        schema = Schema(
            file_name=TEXT(stored=True),
            file_path=TEXT(stored=True),
            file_content=TEXT(analyzer=ChineseAnalyzer())
        )


        # 重新开启数据库连接
        cursor = conn.cursor()
        # 查询数据库
        cursor.execute("SELECT file_path, file_name, file_content FROM indexed WHERE status='chkchng'")


        if len(cursor.fetchall()) == 0:
            # logging.debug(f"iiiiiiiiii {cursor.fetchall()}")
            # 如果数据库中没有status='chkchng'，即所有数据都被索引，状态为 status='indexed'，则跳过重建索引
            logging.info("No file changed, skip index")
            pass
        else:
            # 如果数据库中有status='chkchng'，即有数据未被索引，则重建索引
            # logging.debug(f"oooooooooo {cursor.fetchall()}")
            logging.info("File changes detected, start index")
            # 删除之前的索引
            # 1. 判断是否存在 index_dir 文件夹
            
            index_dir = os.path.join(script_dir, "data/index_dir")
            if not os.path.exists(index_dir):
                # 2. 如果不存在则创建 index_dir 文件夹
                os.makedirs(index_dir)
                # 创建索引
                ix = create_in(index_dir, schema)
                writer = ix.writer()
                logging.debug("Created index schema and writer")
            else:
                # 3. 如果存在 index_dir 文件夹则清空该文件夹内所有文件及目录
                for filename in os.listdir(index_dir):
                    file_path = os.path.join(index_dir, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logging.debug(f"Failed to delete {file_path}. Reason: {e}")
                # 创建索引        
                ix = create_in(index_dir, schema)
                writer = ix.writer()
                logging.debug("Created index schema and writer")

            cursor.execute("SELECT file_path, file_name, file_content FROM indexed")
            for row in cursor.fetchall():
                # logging.debug(row)
                if row is None:
                    logging.info("All files index done")
                    break
                else:            
                    file_path, file_name, file_content = row
                    # 分词索引
                    index_file_content(file_path, file_name, file_content, writer)
                    # logging.info(f"Indexed file. {file_name}")
                    # 更新数据库
                    cursor.execute("UPDATE indexed SET status='indexed' WHERE file_path=?", (file_path,))
                    logging.info(f"Indexed and updated db {file_path}.")
            writer.commit()
            ix.close()
            logging.debug("Closed index writer.")

    cursor.close()
    conn.close()
    logging.debug("Closed database connection.")

if __name__ == "__main__":
    main()
