#!/bin/bash
echo "Starting supervisord..."
bin/supervisord -c conf/gunicorn.conf
echo "Supervisord started."