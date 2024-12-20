import os
import logging.config
import configparser
import atexit
import sqlite3
from whoosh.index import open_dir
from whoosh.qparser import QueryParser
from flask import (
    Flask,
    request,
    render_template,
    render_template_string,
    redirect,
    url_for,
    jsonify,
    Response,
)
import markdown
from markdown.extensions.toc import TocExtension
from markdown.extensions.tables import TableExtension
from markdown.extensions.fenced_code import FencedCodeExtension
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.nl2br import Nl2BrExtension
from markdown.extensions.sane_lists import SaneListExtension
from markdown.extensions.smarty import SmartyExtension
from markdown.extensions.wikilinks import WikiLinkExtension
from markdown.extensions.admonition import AdmonitionExtension
from markdown.extensions.attr_list import AttrListExtension
from markdown.extensions.def_list import DefListExtension
from markdown.extensions.footnotes import FootnoteExtension
from markdown.extensions.meta import MetaExtension
from markdown.extensions.abbr import AbbrExtension
from markdown.extensions.legacy_em import LegacyEmExtension
from markdown.extensions.md_in_html import MarkdownInHtmlExtension
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote



# 脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 配置文件路径
CONFIG_FILE = os.path.join(SCRIPT_DIR, "data/config", "config.ini")
# 日志文件路径
LOG_FILE = os.path.join(SCRIPT_DIR, "data/logs", "searcher.log")
# Whoosh 索引存储的目录
INDEX_DIR = os.path.join(SCRIPT_DIR, "data", "index_dir")
# 数据库文件路径
db_file_path = os.path.join(SCRIPT_DIR, "data", "index.db")

# 配置解析器
config = configparser.ConfigParser()
config.read(CONFIG_FILE)

# 获取 folders 配置项的值，并将其分割成列表
FOLDER_NAMES = [folder.strip() for folder in config["Folders"]["folders"].split(",")]
# 构建 BASE_DIR 列表，包含 data 文件夹下所有子目录的完整路径

# BASE_DIR，指的是data文件夹
BASE_DIR = os.path.join(SCRIPT_DIR, "data")
DEL_BASE_DIR = tuple(
    [os.path.join(SCRIPT_DIR, "data", folder_name) for folder_name in FOLDER_NAMES]
)

# 从配置文件中读取日志等级
LOG_LEVEL = getattr(logging, config["Logging"]["log_level"].upper())

# 检查日志文件路径是否存在，如果不存在则创建
log_dir = os.path.dirname(LOG_FILE)
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 创建日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# 创建文件处理器
file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5
)
file_handler.setLevel(LOG_LEVEL)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(LOG_LEVEL)

# 创建日志格式化器
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 将处理器添加到日志记录器
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# 配置 Markdown 扩展
MARKDOWN_EXTENSIONS = [
    TocExtension(),  # 支持目录
    TableExtension(),  # 支持表格
    FencedCodeExtension(),  # 支持代码块
    CodeHiliteExtension(),  # 代码高亮
    Nl2BrExtension(),  # 将一个回车视为换行
    SaneListExtension(),  # 支持列表
    SmartyExtension(),  # 支持智能符号
    WikiLinkExtension(),  # 支持 Wiki 链接
    AdmonitionExtension(),  # 支持提示框
    AttrListExtension(),  # 支持属性列表
    DefListExtension(),  # 支持定义列表
    FootnoteExtension(),  # 支持脚注
    MetaExtension(),  # 支持元数据
    AbbrExtension(),  # 支持缩写
    LegacyEmExtension(),  # 支持旧版强调
    MarkdownInHtmlExtension(),  # 支持 HTML 中的 Markdown
]

# 打开现有的 Whoosh 索引
try:
    ix = open_dir(INDEX_DIR)
except Exception as e:
    logging.debug(f"Error opening index: {e}")
    exit(1)


# 注册一个函数，在应用退出时关闭索引
def close_index():
    ix.close()


atexit.register(close_index)


def search_index(query_str):
    results = []
    try:
        if query_str == "root:":
            for folder_name in FOLDER_NAMES:
                folder_path = os.path.join(BASE_DIR, folder_name)
                results.append(
                    {
                        "file_name": folder_name,
                        "folder_name": folder_name,
                        "folder_path": folder_path,
                        "score": 1,
                    }
                )
        elif query_str.startswith("ls:"):
            dir_name = query_str.split(":", 1)[1].strip()
            dir_path = os.path.join(BASE_DIR, dir_name)
            if dir_path not in DEL_BASE_DIR:
                return results
            if os.path.isdir(dir_path):
                for root, _, files in os.walk(dir_path):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        folder_path = os.path.dirname(file_path)
                        results.append(
                            {
                                "file_name": file_name,
                                "file_path": file_path,
                                "folder_path": folder_path,
                                "score": 1,
                            }
                        )
            else:
                return results
        else:
            with ix.searcher() as searcher:
                parser = QueryParser("file_content", ix.schema)
                query = parser.parse(query_str)
                for hit in searcher.search(query, limit=None):
                    file_path = hit["file_path"]
                    file_name = hit["file_name"]
                    folder_path = os.path.dirname(file_path)
                    folder_name = os.path.basename(folder_path)
                    score = hit.score
                    results.append(
                        {
                            "file_name": file_name,
                            "file_path": file_path,
                            "folder_path": folder_path,
                            "folder_name": folder_name,
                            "score": score,
                        }
                    )
    except Exception as e:
        return results
    return results


app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search", methods=["GET"])
def search():
    query_str = request.args.get("q")
    if not query_str:
        return redirect(url_for("index"))

    try:
        results = search_index(query_str)
        return render_template("results.html", query=query_str, results=results)
    except Exception as e:
        return redirect(url_for("index")), 500


@app.route("/iframe_default")
def iframe_default():
    return render_template("iframe_default.html")


@app.route("/render_file")
def render_file():
    file_path = request.args.get("path")
    query_str = request.args.get("query")

    # 解码文件路径
    file_path = unquote(file_path)

    if not file_path or not os.path.exists(file_path):
        return render_template("iframe_default.html"), 404

    try:
        file_extension = os.path.splitext(file_path)[1]

        if file_extension in ['.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.csv', '.json', '.xml','.md']:
            with sqlite3.connect(db_file_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT file_content FROM indexed WHERE file_path = ?", (file_path,))
                row = cursor.fetchone()
                if row:
                    content = row[0]
                else:
                    content = ""
            rendered_content = markdown.markdown(
                content, extensions=MARKDOWN_EXTENSIONS
            )
            if query_str:
                soup = BeautifulSoup(rendered_content, "html.parser")
                pattern = re.compile(re.escape(query_str), re.IGNORECASE)
                for text_node in soup.find_all(text=True):
                    if text_node.parent.name not in [
                        "script",
                        "style",
                        "code",
                    ]:
                        highlighted_text = pattern.sub(
                            f'<span style="background-color: yellow;">{query_str}</span>',
                            text_node,
                        )
                        text_node.replace_with(
                            BeautifulSoup(highlighted_text, "html.parser")
                        )
                rendered_content = str(soup)
            custom_css_link = "<link rel=\"stylesheet\" href=\"{{ url_for('static', filename='markdown_styles.css') }}\">"
            rendered_content = render_template_string(
                f"{custom_css_link}<div>{rendered_content}</div>", url_for=url_for
            )
        elif file_extension == ".html":
            with open(file_path, "r", encoding="utf-8") as file:
                rendered_content = file.read()
        else:
            with open(file_path, "rb") as file:
                content = file.read()
            rendered_content = f"<html><body><pre>{content.decode('utf-8', errors='replace')}</pre></body></html>"

        rendered_content += """
        <script>
            let touchStartX = 0;
            let touchEndX = 0;

            document.addEventListener('touchstart', function (event) {
                touchStartX = event.changedTouches[0].screenX;
            });

            document.addEventListener('touchend', function (event) {
                touchEndX = event.changedTouches[0].screenX;
                handleSwipe();
            });

            function handleSwipe() {
                const swipeDistance = touchEndX - touchStartX;
                if (swipeDistance > 50) {
                    window.parent.postMessage('showList', '*');
                } else if (swipeDistance < -50) {
                    window.parent.postMessage('hideList', '*');
                }
            }
        </script>
        """

        return rendered_content
    except UnicodeDecodeError as e:
        return Response(f"Error reading file: {str(e)}", status=500), 500
    except Exception as e:
        return Response(f"An error occurred: {str(e)}", status=500), 500

@app.route("/delete_file", methods=["DELETE"])
def delete_file():
    file_path = request.args.get("path")
    if not file_path:
        return jsonify({"error": "缺少文件路径"}), 400

    if not file_path.startswith(DEL_BASE_DIR):
        return jsonify({"error": "文件超出允许的目录"}), 400

    try:
        os.remove(file_path)
        logger.info(f"文件 '{file_path}' 已成功删除。")
        return jsonify({"message": "文件已成功删除"}), 200
    except FileNotFoundError:
        logger.error(f"删除文件 '{file_path}' 时出错: 找不到文件")
        return jsonify({"error": "找不到文件"}), 404
    except Exception as e:
        logger.error(f"删除文件 '{file_path}' 时出错: {e}")
        return jsonify({"error": "删除文件失败"}), 500


if __name__ == "__main__":
    app.run()
