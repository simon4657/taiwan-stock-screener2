#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gunicorn配置文件 - 台股主力資金篩選器上市市場版本

重要說明：
- 使用單一 worker（workers=1）確保全域變數（stocks_data、update_status）在所有請求間共享
- 多 worker 會導致後台執行緒和全域狀態無法跨 worker 共享
- 使用 gevent worker 支援非同步 I/O，避免長時間請求阻塞
"""

# 服務器配置
bind = "0.0.0.0:5000"
workers = 1  # 必須使用單一 worker，確保全域變數共享（stocks_data, update_status）
worker_class = "gevent"  # 使用 gevent 支援非同步 I/O
worker_connections = 1000
timeout = 600  # 增加超時時間到 10 分鐘（Yahoo Finance 批次下載需要約 2 分鐘）
keepalive = 5

# 日誌配置
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# 進程配置
max_requests = 0  # 禁用自動重啟（避免更新中途被重啟）
max_requests_jitter = 0
preload_app = False

# 安全配置
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 啟動配置
graceful_timeout = 120
worker_tmp_dir = "/dev/shm"  # 使用內存文件系統加速
