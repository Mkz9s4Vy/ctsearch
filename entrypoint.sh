#!/bin/bash
echo "Starting supervisord..."
supervisord -c gunicorn.conf
echo "Supervisord started."