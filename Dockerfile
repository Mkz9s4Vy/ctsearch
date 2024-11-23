FROM python:3-alpine

RUN addgroup -g 1000 appgroup && \
    adduser -D -u 1000 -G appgroup appuser && \
    mkdir /app
# RUN mkdir /app

WORKDIR /app

COPY ["requirements.txt", "indexer.py /app", "searcher.py /app", "watcher.py /app", "webdav_server.py", "supervisord.conf", "docker-entrypoint.sh", "/app/"]

# COPY requirements.txt /app

# COPY indexer.py /app

# COPY searcher.py /app

# COPY watcher.py /app

# COPY webdav_server.py /app

# COPY supervisord.conf /app

# COPY docker-entrypoint.sh /app

COPY init/ /app/init/

COPY static/ /app/static/

COPY templates/ /app/templates/


RUN pip install --no-cache -r requirements.txt && \
    chmod +x /app/docker-entrypoint.sh

# RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000
EXPOSE 8192

ENTRYPOINT ["/app/docker-entrypoint.sh"]
