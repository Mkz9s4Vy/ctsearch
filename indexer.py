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
from tokenizer import create_index, open_index, add_document_to_index, delete_document_from_index



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



# 创建数据库和表
def create_database(db_path):
    # if not os.path.exists(db_path):
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

# 删除索引目录并重新创建
def remove_index_dir(index_dir):
    if not os.path.exists(index_dir):
        os.makedirs(index_dir)
        logging.debug("Created index directory")
    else:
        shutil.rmtree(index_dir)
        os.makedirs(index_dir)
        logging.debug("Created index directory")

# 扫描文件夹
def scan_folder(folder_path, conn):
    for root, _, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_path = file_path.encode('utf-8', errors='ignore').decode('utf-8')
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension in ['.docx', '.pptx', '.xlsx', '.csv', '.json', '.xml','.html','.md']:
                file_attributes = get_file_attributes(file_path)
                if file_attributes:
                    insert_file_attributes_to_db(conn, [file_attributes])
            else:
                logging.info(f"Skipped file with unsupported extension: {file_path}")


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
            'status': 'waiting_to_index'
        }
    except Exception as e:
        logging.error(f"Error getting file attributes for {file_path}: {e}")
        return None


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


# 解析Markdown文件
def parse_md(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            return content
    except Exception as e:
        logging.error(f"Error parsing Markdown file {file_path}: {e}")
        return None

# 解析非 markdown 文件
def parse_to_md(file_path):
    try:
        md = MarkItDown()
        result = md.convert(file_path)
        content = result.text_content
        return content
    except Exception as e:
        logging.error(f"Error parsing file {file_path}: {e}")
        return None

# 解析文件
def parse_file(file_path, extension):
    if extension == '.md':
        return parse_md(file_path)
    elif extension in ['.docx', '.pptx', '.xlsx', '.csv', '.json', '.xml','.html','.md']:
        return parse_to_md(file_path)
    else:
        raise ValueError(f"Unsupported file extension: {extension}")

# 主函数
def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "data/config","config.ini")
    log_file_path = os.path.join(script_dir, "data/logs","logs.log")
    db_file_path = os.path.join(script_dir, "data", "index.db")
    index_dir = os.path.join(script_dir, "data", "index_dir")

    # 如果日志文件不存在则创建
    if not os.path.exists(log_file_path):
        with open(log_file_path, 'a'):
            os.utime(log_file_path, None)

    config = read_config(config_path, script_dir)
    setup_logging(log_file_path, config['log_level'])

    # 如果数据库不存在则创建数据库和重建索引目录
    if not os.path.exists(db_file_path):
        create_database(db_file_path)
        # 如果重建数据库则重建索引目录
        remove_index_dir(index_dir)


    # 准备数据库指针
    with sqlite3.connect(db_file_path) as conn:
        cursor = conn.cursor()
        # 扫描目录并将文件元数据插入数据库
        for folder in config['folders']:
            scan_folder(folder, conn)
        

        # 准备索引指针
        # 索引目录是否存在索引
        if not exists_in(index_dir):
            ix = create_index(index_dir)
        else:
            ix = open_index(index_dir)
        writer = ix.writer()


        # 整理数据库，整理索引
        # 删除、添加、更新
        cursor.execute("SELECT i.file_path FROM indexed i LEFT JOIN chkchng c ON i.file_path = c.file_path WHERE c.file_path IS NULL")
        delete_paths = [item[0] for item in cursor.fetchall()]

        cursor.execute("SELECT i.file_path FROM indexed i INNER JOIN chkchng c ON i.file_path = c.file_path WHERE i.modification_time <> c.modification_time")
        update_paths = [item[0] for item in cursor.fetchall()]

        # 删除已经不存在文件的索引和删除有修改的文件的索引
        remove_index_paths = delete_paths + update_paths
        for remove_index_path in remove_index_paths:
            delete_document_from_index(writer, remove_index_path)
            logging.info(f"Deleted file from index: {remove_index_path}")
        writer.commit()

        # 删除 indexed 表中有的，但 chkchng 表中没有的数据
        cursor.execute("DELETE FROM indexed WHERE file_path NOT IN (SELECT file_path FROM chkchng)")
        logging.info(f"Deleted files from db for not exist {delete_paths}")

        # 删除 indexed 表中，那些 file_path 在 chkchng 表中也存在，但 modification_time 不同的记录
        cursor.execute("DELETE FROM indexed WHERE EXISTS (SELECT 1 FROM chkchng WHERE chkchng.file_path = indexed.file_path AND chkchng.modification_time <> indexed.modification_time)")
        logging.info(f"Deleted files from db for modified {delete_paths}")


        try:
            # 查询需要处理的文件路径
            writer = ix.writer()
            cursor.execute("""
                SELECT c.file_path, c.file_name, c.extension, c.file_type, 
                    c.creation_time, c.modification_time, c.file_size, 
                    c.is_hidden
                FROM chkchng c
                LEFT JOIN indexed i ON c.file_path = i.file_path
                WHERE i.file_path IS NULL
            """)

            files_to_process = cursor.fetchall()
            data_to_insert = []

            for row in files_to_process:
                file_path = row[0]
                extension = row[2]

                try:
                    content = parse_file(file_path, extension)
                    if content:
                        # 构建需要插入的数据
                        data_to_insert.append(row + ('indexed', content))
                        # Whoosh 索引
                        add_document_to_index(writer, file_path, row[1], content)  # 使用row[1]作为文件名
                        logging.info(f"Parsed and indexed file: {file_path}")
                    else:
                        logging.error(f"Failed to parse file: {file_path}")           

                except Exception as e:
                    logging.error(f"Error processing file {file_path}: {e}")

            # 批量插入数据
            if data_to_insert:  
                cursor.executemany("INSERT INTO indexed (file_path, file_name, extension, file_type, creation_time, modification_time, file_size, is_hidden, status, file_content) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", data_to_insert)
                conn.commit()
                logging.info(f"Indexed {len(data_to_insert)} files.")

        except Exception as e:
            conn.rollback()
            writer.cancel()
            logging.error(f"An error occurred: {e}")

        # 清空 chkchng 表
        cursor.execute("DELETE FROM chkchng")
        conn.commit()

    cursor.close()
    conn.close()
    writer.commit()
    ix.close

if __name__ == "__main__":
    main()
