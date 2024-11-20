FROM python:3-alpine

RUN addgroup -g 1000 appgroup && \
    adduser -D -u 1000 -G appgroup appuser

RUN mkdir /app

WORKDIR /app

COPY . /app

RUN pip install --no-cache -r requirements.txt

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000
EXPOSE 8192

ENTRYPOINT ["/app/docker-entrypoint.sh"]
