#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gunicorn配置文件 - 台股主力資金篩選器上櫃市場版本
"""

import multiprocessing

# 服務器配置
bind = "0.0.0.0:5000"
workers = min(2, multiprocessing.cpu_count())  # 減少worker數量以加快啟動
worker_class = "sync"
worker_connections = 1000
timeout = 300  # 增加超時時間到5分鐘
keepalive = 2

# 日誌配置
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# 進程配置
max_requests = 1000
max_requests_jitter = 100
preload_app = False  # 改為False以避免預載入時的數據更新

# 安全配置
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 啟動配置
graceful_timeout = 60  # 優雅關閉超時
worker_tmp_dir = "/dev/shm"  # 使用內存文件系統加速

