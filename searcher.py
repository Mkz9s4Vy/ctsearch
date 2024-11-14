import os
from whoosh.index import open_dir
from whoosh.qparser import QueryParser
import atexit
from flask import Flask, request, render_template, render_template_string, redirect, url_for, jsonify
import os
import markdown
from markdown.extensions.nl2br import Nl2BrExtension
import docx
import pptx



# 脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))
# 定义 Whoosh 索引存储的目录
index_dir = os.path.join(script_dir, "data/index_dir")


# 配置 Markdown 扩展
markdown_extensions = [
    Nl2BrExtension(),  # 将一个回车视为换行
]


# 打开现有的 Whoosh 索引
try:
    ix = open_dir(index_dir)
except Exception as e:
    print(f"Error opening index: {e}")
    exit(1)

# 注册一个函数，在应用退出时关闭索引
def close_index():
    ix.close()

atexit.register(close_index)

# 搜索索引的函数
def search_index(query_str):
    results = []
    try:
        with ix.searcher() as searcher:
            parser = QueryParser("file_content", ix.schema)
            query = parser.parse(query_str)
            for hit in searcher.search(query):
                file_path = hit['file_path']
                file_name = hit['file_name']
                folder_path = os.path.dirname(file_path)
                score = hit.score  # Assuming Whoosh provides a score
                results.append({
                    "file_name": file_name,
                    "file_path": file_path,
                    "folder_path": folder_path,
                    "score": score
                })
    except Exception as e:
        print(f"Error during search: {e}")
    return results


app = Flask(__name__)

# 定义默认界面
@app.route('/')
def index():
    return render_template('index.html')


# 定义搜索路由
@app.route('/search', methods=['GET'])
def search():
    query_str = request.args.get('q')
    if not query_str:
        return redirect(url_for('index')) # 重定向到根目录
    
    try:
        results = search_index(query_str)
        # return jsonify(results)
        return render_template('results.html', query=query_str, results=results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        # return render_template('error.html', message='No query provided')

@app.route('/render_file')
def render_file():
    file_path = request.args.get('path')
    if not file_path or not os.path.exists(file_path):
        return "File not found", 404
    
    try:
        file_extension = os.path.splitext(file_path)[1]
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        if file_extension == '.md':
            # 渲染 Markdown 文件
            rendered_content = markdown.markdown(content, extensions=markdown_extensions)
            # 使用 render_template_string 函数来渲染包含 Jinja2 语法的字符串
            custom_css_link = '<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'markdown_styles.css\') }}">'
            rendered_content = render_template_string(f"{custom_css_link}<div>{rendered_content}</div>", url_for=url_for)
        elif file_extension == '.html':
            # 直接返回 HTML 文件内容
            rendered_content = content
        elif file_extension == '.docx':
            # 渲染 DOCX 文件
            doc = docx.Document(file_path)
            rendered_content = "<html><body><h1>{}</h1>".format(doc.core_properties.title)
            for para in doc.paragraphs:
                rendered_content += "<p>{}</p>".format(para.text)
            rendered_content += "</body></html>"
        elif file_extension == '.pptx':
            # 渲染 PPT 文件
            prs = pptx.Presentation(file_path)
            rendered_content = "<html><body><h1>{}</h1>".format(prs.core_properties.title)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        rendered_content += "<p>{}</p>".format(shape.text)
            rendered_content += "</body></html>"
        else:
            # 其他文件类型，直接返回文本内容
            rendered_content = f"<html><body><pre>{content}</pre></body></html>"
        
        return rendered_content
    except Exception as e:
        return f"Error rendering file: {str(e)}", 500




if __name__ == '__main__':
    app.run(debug=True)
