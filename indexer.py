import os
import os.path
import sqlite3
import configparser
import queue
import time
import logging
from logging.handlers import RotatingFileHandler
import shutil
import jieba.analyse
from jieba.analyse import ChineseAnalyzer
from whoosh.fields import Schema, TEXT, ID
from whoosh.index import create_in, open_dir, exists_in
from markitdown import MarkItDown

# 读取配置文件
def read_config(config_file, script_dir):
    config = configparser.ConfigParser()
    config.read(config_file)
    # 解析 folders 配置项
    folders = [folder.strip() for folder in config['Folders']['folders'].split(',')]
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

def scan_folder(folder_path, conn):
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_path = file_path.encode('utf-8', errors='ignore').decode('utf-8')
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension in ['.docx', '.pptx', '.xlsx', '.csv', '.json', '.xml','.html']:
                file_attributes = get_file_attributes(file_path)
                if file_attributes:
                    insert_file_attributes_to_db(conn, [file_attributes])
            else:
                logging.info(f"Skipped file with unsupported extension: {file_path}")

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
    db_op_count = 0
    reindex_needed = False

    cursor.execute("SELECT file_path, modification_time FROM chkchng")
    chkchng_data = cursor.fetchall()
    cursor.execute("SELECT file_path, modification_time FROM indexed")
    indexed_data = cursor.fetchall()

    chkchng_dict = {item[0]: item[1] for item in chkchng_data}
    indexed_dict = {item[0]: item[1] for item in indexed_data}

    for file_path in indexed_dict:
        if file_path not in chkchng_dict:
            delete_from_indexed(cursor, file_path)
            db_op_count += 1

    for file_path, chkchng_mod_time in chkchng_dict.items():
        if file_path not in indexed_dict:
            insert_into_indexed(cursor, file_path)
            db_op_count += 1
        else:
            indexed_mod_time = indexed_dict[file_path]
            if chkchng_mod_time != indexed_mod_time:
                update_indexed(cursor, file_path)
                db_op_count += 1

    cursor.execute("DELETE FROM chkchng")
    logging.debug("Cleared chkchng table.")
    conn.commit()
    
    if db_op_count != 0:
        reindex_needed = True
        logging.debug(f"数据库增删改操作计数 - {db_op_count}")
        return reindex_needed
    else:
        reindex_needed = False
        logging.debug(f"数据库增删改操作计数 - {db_op_count}")
        return reindex_needed
    
# 数据库增删改操作函数
def delete_from_indexed(cursor, file_path):
    cursor.execute("DELETE FROM indexed WHERE file_path=?", (file_path,))
    logging.info(f"Removed files from indexed table {file_path}.")

def insert_into_indexed(cursor, file_path):
    cursor.execute("INSERT INTO indexed SELECT *, NULL FROM chkchng WHERE file_path=?", (file_path,))
    logging.info(f"Added files to indexed table {file_path}.")

def update_indexed(cursor, file_path):
    cursor.execute("DELETE FROM indexed WHERE file_path=?", (file_path,))
    cursor.execute("INSERT INTO indexed SELECT *, NULL FROM chkchng WHERE file_path=?", (file_path,))
    logging.info(f"Updated files in indexed table {file_path}.")

# 解析Markdown文件
def parse_md(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            return content
    except Exception as e:
        logging.error(f"Error parsing Markdown file {file_path}: {e}")
        return None

def parse_to_md(file_path):
    try:
        md = MarkItDown()
        result = md.convert(file_path)
        content = result.text_content
        return content
    except Exception as e:
        logging.error(f"Error parsing file {file_path}: {e}")
        return None

def parse_file(file_path, extension):
    if extension == '.md':
        return parse_md(file_path)
    elif extension in ['.docx', '.pptx', '.xlsx', '.csv', '.json', '.xml','.html']:
        return parse_to_md(file_path)
    else:
        raise ValueError(f"Unsupported file extension: {extension}")

def index_file_content(file_path, file_name, file_content, writer):
    wait_index_content = file_path + file_content
    segmented_content = " ".join(jieba.cut_for_search(wait_index_content, HMM=True))
    writer.add_document(file_name=file_name, file_path=file_path, file_content=segmented_content)

# 设置日志格式
def setup_logging(log_file_path, log_level):
    logger = logging.getLogger()
    logger.setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = RotatingFileHandler(log_file_path, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    jieba_logger = logging.getLogger(jieba.__name__)
    jieba_logger.setLevel(log_level)
    jieba_logger.addHandler(file_handler)

# 主函数
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "data/config","config.ini")
    db_file_path = os.path.join(script_dir, "data/index.db")
    log_file_path = os.path.join(script_dir, "data/logs","logs.log")

    if not os.path.exists(log_file_path):
        with open(log_file_path, 'a'):
            os.utime(log_file_path, None)

    config = read_config(config_path, script_dir)
    setup_logging(log_file_path, config['log_level'])

    create_database_if_not_exists(db_file_path)
    
    with sqlite3.connect(db_file_path) as conn:
        # 扫描文件夹并将文件元数据插入数据库
        for folder in config['folders']:
            scan_folder(folder, conn)
        
        # 对比和更新数据库
        reindex_needed = compare_and_update_db(conn)
        logging.info(f"Reindex needed: {reindex_needed}")

        if reindex_needed:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path, extension FROM indexed WHERE file_content IS NULL")
            files_to_parse = cursor.fetchall()

            for file_path, extension in files_to_parse:
                content = parse_file(file_path, extension)
                if content:
                    cursor.execute("UPDATE indexed SET file_content=? WHERE file_path=?", (content, file_path))
                    logging.info(f"Parsed and updated file content {file_path}.")

            conn.commit()

            schema = Schema(
                file_name=TEXT(stored=True),
                file_path=TEXT(stored=True),
                file_content=TEXT(analyzer=ChineseAnalyzer())
            )

            index_dir = os.path.join(script_dir, "data/index_dir")
            if not os.path.exists(index_dir):
                os.makedirs(index_dir)
                ix = create_in(index_dir, schema)
                writer = ix.writer()
                logging.debug("Created index schema and writer")
            else:
                for filename in os.listdir(index_dir):
                    file_path = os.path.join(index_dir, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logging.debug(f"Failed to delete {file_path}. Reason: {e}")
                ix = create_in(index_dir, schema)
                writer = ix.writer()
                logging.debug("Created index schema and writer")
            
            cursor = conn.cursor()
            cursor.execute("SELECT file_path, file_name, file_content FROM indexed")
            for row in cursor.fetchall():
                if row is None:
                    logging.info("All files index done")
                    break
                else:            
                    file_path, file_name, file_content = row
                    index_file_content(file_path, file_name, file_content, writer)
                    cursor.execute("UPDATE indexed SET status='indexed' WHERE file_path=?", (file_path,))
                    logging.info(f"Indexed and updated db {file_path}.")

            writer.commit()
            ix.close()
            logging.debug("Closed index writer.")

            conn.commit()
            logging.debug("Closed database connection.")

            logging.info("本次索引完成")
        else:
            logging.info("No thing to do.")

if __name__ == "__main__":
    main()
