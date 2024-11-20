# webdav_server.py
import os
import yaml
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.dir_browser import WsgiDavDirBrowser
from wsgidav.dc.simple_dc import SimpleDomainController
from cheroot.wsgi import Server as WSGIServer

# 读取配置文件
config_path = os.path.join(os.path.dirname(__file__), 'data/config', 'webdav_config.yaml')
with open(config_path, 'r') as file:
    config = yaml.safe_load(file)

# 设置 WebDAV 应用
app = WsgiDAVApp(config)

# 启动服务器
server_args = {
    'bind_addr': (config['host'], config['port']),
    'wsgi_app': app,
}
server = WSGIServer(**server_args)

if __name__ == "__main__":
    try:
        print(f"Serving on http://{config['host']}:{config['port']} ...")
        server.start()
    except KeyboardInterrupt:
        server.stop()
