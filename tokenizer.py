import os
import logging
from whoosh.fields import Schema, TEXT, ID
from whoosh.index import create_in, open_dir
import jieba.analyse
from jieba.analyse import ChineseAnalyzer






def create_index(index_dir):
    """
    创建 Whoosh 索引
    """
    schema = Schema(
        file_name=TEXT(stored=True),
        file_path=ID(stored=True),
        file_content=TEXT(analyzer=ChineseAnalyzer())
    )
    ix = create_in(index_dir, schema)
    return ix

def open_index(index_dir):
    """
    打开 Whoosh 索引
    """
    ix = open_dir(index_dir)
    logging.debug("Opened existing index")
    return ix

def add_document_to_index(writer, file_path, file_name, file_content):
    """
    将文档添加到 Whoosh 索引中。
    """
    file_content = str(file_name + file_content)
    segmented_content = " ".join(jieba.cut_for_search(file_content, HMM=True))
    writer.add_document(file_name=file_name, file_path=file_path, file_content=segmented_content)
    logging.debug(f"Indexed file: {file_path}")

def delete_document_from_index(writer, file_path):
    """
    从 Whoosh 索引中删除指定的文档。
    """
    writer.delete_by_term("file_path", file_path)
    logging.debug(f"Deleted file from index: {file_path}")

def commit_index(writer):
    """
    提交索引更改。
    """
    writer.commit()
    logging.debug("Committed index changes.")
