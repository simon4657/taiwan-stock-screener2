# Gunicorn配置檔案 - 解決WORKER TIMEOUT問題

# 基本配置
bind = "0.0.0.0:10000"
workers = 1

# 超時配置（關鍵修復）
timeout = 300  # 從30秒增加到300秒（5分鐘）
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

# 工作進程配置
worker_class = "sync"  # 使用同步工作模式
worker_connections = 1000
preload_app = True

# 日誌配置
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 進程管理
graceful_timeout = 30
tmp_upload_dir = None

# 安全配置
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# 效能優化
worker_tmp_dir = "/dev/shm"  # 使用記憶體檔案系統

