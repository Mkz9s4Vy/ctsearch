## 简介
本项目所有代码均由 AI 完成，作者只负责提出需求，确定实现方案，测试代码。

本项目是一个用于扫描、索引和管理文件的工具。它能够自动扫描指定文件夹中的文件，对文件内容进行解析并建立索引，提供了一个网页来搜索和查看文件内容。


## 功能特性
文件扫描：自动扫描指定文件夹中的所有文件。

文件解析：支持对Markdown、HTML、Docx 和 PPTX 文件的内容进行解析和索引。

分词索引：使用 jieba 分词对文件内容进行分词和全文索引。

Web界面：提供一个基于Flask的Web界面，用户可以通过该界面进行文件搜索、查看文件内容以及删除文件。

文件监控：使用watchdog库监控指定文件夹，当文件夹内容发生变化时自动触发索引更新。

WebDAV服务器：提供一个基于WebDAV协议的服务器，用户可以通过WebDAV客户端访问和管理文件。



## 技术细节
indexer.py，用于文件解析和索引。使用各种库对文件内容进行解析，然后使用 jieba 分词将解析后的纯文本内容分词索引，并将索引结果存入 Whoosh 中。

searcher.py，用于文件内容搜索和建立用户界面。使用 Flask 建立用户界面，调用 Whoosh 进行搜索。

watcher.py，用于文件变动监控。使用 watchdog 监控文件的创建、删除、修改操作，并调用 indexer 进行扫描和索引。

webdav_server.py，用于建立 WebDav 服务器。使用 wsgidav 建立 WebDAV 服务器，提供文件上传入口。

supervisord.conf，用于使用 supervisord 拉起和管理上述各项服务。



## Docker 部署
### 1. 拉取镜像文件

`docker pull ghcr.io/mkz9s4vy/ctsearch:ver2024-11-23`

### 2. 准备放置数据的文件夹，假设为 `~/ctsearch`

`mkdir ~/ctsearch`

### 3. 生成配置文件

`docker run --rm --name=ctsearch -v ~/ctsearch:/app/data ghcr.io/mkz9s4vy/ctsearch:ver2024-11-23`

删除刚刚的容器。

`docker stop ctsearch && docker rm ctsearch`

此时 `ctsearch` 目录的结构应该如下：

```
.
├── config
│   ├── config.ini  # 项目配置文件
│   └── webdav_config.yaml  # WebDAV 服务配置文件
├── index.db  # sqlite 数据库（未加密），用于存储和对比文件元数据，也用于存储解析后的文件内容
├── index_dir  # jieba 分词索引目录
│   ├── MAIN_WRITELOCK
│   ├── MAIN_ruj990a3r7dpxg3y.seg
│   └── _MAIN_1.toc
├── logs
│   ├── logs.log  # 文件解析、索引的日志
│   ├── searcher.log  # 只保存用户界面删除文件的日志，不保存用户搜索相关内容
│   ├── supervisord.log  # supervisord 管理服务的日志
│   └── watcher.log  # 文件夹和文件变动监控日志
└── webdata  # 通过 WebDAV 服务上传的文件存放目录
```


### 4. 修改配置文件

修改以下两个文件，`config/config.ini` 和 `config/webdav_config.yaml`。

#### 4.1 修改 config.ini

主要修改 `folders = input, webdata`。

把需要监控、解析和索引的文件夹写在这一行，以半角逗号分隔。

`input` 是示例条目，可以删除。

`webdata` 是 WebDAV 服务器存放上传文件的目录。不建议删除或修改，如果要修改请自行解决问题。


#### 4.2 修改 webdav_config.yaml

主要修改 `username` 和 `your_password`。

修改其他部分请自行查阅相关文档。


### 5. 修改完成后，启动容器

```
docker run -d --name=ctsearch -p 8000:8000 -p 8192:8192 -v ~/ctsearch:/app/data ghcr.io/mkz9s4vy/ctsearch:ver2024-11-23
```

`8000` 端口是 Flask 应用入口，访问 `ip:8000` 即可以进行搜索内容，预览文件和删除文件。

`8192` 端口是 WebDAV 服务端口。


## Podman 部署

### 1. 拉取镜像文件

`podman pull ghcr.io/mkz9s4vy/ctsearch:ver2024-11-23`

### 2. Quadlet 文件

```
[Unit]
Description=ctsearch

[Container]
AutoUpdate=registry
ContainerName=ctsearch
Image=ghcr.io/mkz9s4vy/ctsearch:ver2024-11-23
PublishPort=8000:8000
PublishPort=8192:8192
Volume=<your_data_path>:/app/data:Z
# 如果你的用户 UID 和 GID不是1000，请自行修改以下内容
UserNS=keep-id:uid=1000,gid=1000

[Service]
Restart=always

[Install]
WantedBy=default.target
```


### 3. 准备放置数据的文件夹，假设为 `~/ctsearch`

`mkdir ~/ctsearch`

### 3. 生成配置文件

`systemctl --user daemon-reload`

`systemctl --user start ctsearch`

`systemctl --user stop ctsearch`

### 4. 修改配置文件

同 Docker 部署 - 步骤4 内容。

### 5. 启动容器

`systemctl --user start ctsearch`

## 应用使用

- 以下功能说明仅针对 `ghcr.io/mkz9s4vy/ctsearch:ver2024-11-23` 版本。

- 在输入框输入内容，再敲击 `Enter` 键即可搜索文件内容。

- 在搜索结果页点击搜索结果条目，可以预览文件内容。仅在预览 Markdown 文件时会高亮搜索词。

- 在搜索结果页点击`Clear` ，或不输入直接点击`search`图标，可以返回搜索主界面。

- 在已经预览文件的前提下，点击 `Clear` 可以清除预览。

- 在已经预览文件的前提下，点击 `Delete` 可以删除文件。**删除后不可找回**。

- 手机端网页使用时，右下角有 `list` 按钮，点击可以打开或关闭搜索结果列表。

- 手机端网页使用时，在搜索结果页左滑或右滑，点击可以打开或关闭搜索结果列表。




## 其他事项

- 用户界面没有任何加密和验证，建议内网个人使用。

- 如需外网访问，请自行使用反向代理，**并且在反向代理开启访问验证**。

- 如果需要重建索引，请删除 `index_dir` 和 `index.db`，然后重启容器。

- 没有任何桌面应用，也不计划制作。

- 可以提 issue，但不接受任何 PR。

- 随缘开发，没有路线图，功能随时增加。




## 免责声明

Mkz9s4Vy/ctsearch 项目，Github链接 `https://github.com/Mkz9s4Vy/ctsearch`，下文称本项目。

- 如有任何疑虑，请不要使用本项目。

- 本项目是作者因个人需求制作，作者不对项目使用造成的任何后果负责。



## 致谢

- [Lobe Chat](https://github.com/lobehub/lobe-chat)

- [DeepSeek](https://www.deepseek.com)


