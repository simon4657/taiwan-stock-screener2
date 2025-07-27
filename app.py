#!/usr/bin/env python3
"""
台股主力資金進入篩選器 - Render部署修復版本
"""

import os
import logging
import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import requests

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 創建Flask應用
app = Flask(__name__)
CORS(app)

# 全域變數
collector = None
calculator = None
stocks_data = {}
last_update_time = None
is_updating = False
initialization_error = None

def safe_import_modules():
    """安全導入模組"""
    global collector, calculator, initialization_error
    
    try:
        # 嘗試導入自定義模組
        from stock_data_collector import StockDataCollector
        from banker_signal_calculator import BankerEntrySignalCalculator
        
        logger.info("成功導入自定義模組")
        
        # 初始化組件
        collector = StockDataCollector()
        calculator = BankerEntrySignalCalculator()
        
        logger.info("組件初始化成功")
        return True
        
    except ImportError as e:
        error_msg = f"模組導入失敗: {e}"
        logger.error(error_msg)
        initialization_error = error_msg
        return False
    except Exception as e:
        error_msg = f"組件初始化失敗: {e}"
        logger.error(error_msg)
        initialization_error = error_msg
        return False

def get_default_stock_list():
    """獲取預設股票清單"""
    return [
        {'stock_id': '2330', 'stock_name': '台積電'},
        {'stock_id': '2317', 'stock_name': '鴻海'},
        {'stock_id': '2454', 'stock_name': '聯發科'},
        {'stock_id': '2881', 'stock_name': '富邦金'},
        {'stock_id': '2882', 'stock_name': '國泰金'},
        {'stock_id': '2412', 'stock_name': '中華電'},
        {'stock_id': '2303', 'stock_name': '聯電'},
        {'stock_id': '1301', 'stock_name': '台塑'},
        {'stock_id': '1303', 'stock_name': '南亞'},
        {'stock_id': '2002', 'stock_name': '中鋼'},
        {'stock_id': '2886', 'stock_name': '兆豐金'},
        {'stock_id': '2891', 'stock_name': '中信金'},
        {'stock_id': '2892', 'stock_name': '第一金'},
        {'stock_id': '2884', 'stock_name': '玉山金'},
        {'stock_id': '2885', 'stock_name': '元大金'},
        {'stock_id': '2883', 'stock_name': '開發金'},
        {'stock_id': '3008', 'stock_name': '大立光'},
        {'stock_id': '2357', 'stock_name': '華碩'},
        {'stock_id': '2382', 'stock_name': '廣達'},
        {'stock_id': '2308', 'stock_name': '台達電'}
    ]

@app.route('/')
def index():
    """主頁面"""
    return render_template('index.html')

@app.route('/api/stocks/list')
def get_stock_list():
    """獲取股票清單API"""
    try:
        if collector and hasattr(collector, 'get_taiwan_stock_list'):
            stock_list = collector.get_taiwan_stock_list()
            if hasattr(stock_list, 'to_dict'):
                return jsonify({
                    'success': True,
                    'data': stock_list.to_dict('records'),
                    'count': len(stock_list)
                })
        
        # 使用預設清單
        default_list = get_default_stock_list()
        return jsonify({
            'success': True,
            'data': default_list,
            'count': len(default_list),
            'note': '使用預設股票清單'
        })
        
    except Exception as e:
        logger.error(f"獲取股票清單失敗: {e}")
        default_list = get_default_stock_list()
        return jsonify({
            'success': True,
            'data': default_list,
            'count': len(default_list),
            'note': '使用預設股票清單（發生錯誤）'
        })

@app.route('/api/stocks/update', methods=['POST'])
def update_stocks():
    """更新股票資料API"""
    global is_updating, last_update_time, stocks_data
    
    try:
        if initialization_error:
            return jsonify({
                'success': False,
                'error': '系統初始化失敗',
                'message': initialization_error
            }), 500
        
        if is_updating:
            return jsonify({
                'success': False,
                'message': '資料更新正在進行中，請稍後查看結果'
            })
        
        # 開始更新
        is_updating = True
        
        def update_task():
            global is_updating, last_update_time, stocks_data
            try:
                logger.info("開始更新股票資料...")
                
                # 獲取股票清單
                if collector:
                    stock_list = collector.get_taiwan_stock_list()
                else:
                    stock_list = get_default_stock_list()
                
                # 模擬資料更新過程
                stocks_data = {}
                if hasattr(stock_list, 'iterrows'):
                    for i, row in stock_list.iterrows():
                        stock_code = row.get('stock_id', row.iloc[0] if len(row) > 0 else '')
                        stocks_data[stock_code] = {
                            'code': stock_code,
                            'name': row.get('stock_name', row.iloc[1] if len(row) > 1 else ''),
                            'updated': True
                        }
                else:
                    for stock in stock_list:
                        stock_code = stock['stock_id']
                        stocks_data[stock_code] = {
                            'code': stock_code,
                            'name': stock['stock_name'],
                            'updated': True
                        }
                
                last_update_time = datetime.now()
                logger.info(f"股票資料更新完成，共 {len(stocks_data)} 支股票")
                
            except Exception as e:
                logger.error(f"更新股票資料時發生錯誤: {e}")
            finally:
                is_updating = False
        
        # 啟動背景任務
        threading.Thread(target=update_task, daemon=True).start()
        
        return jsonify({
            'success': True,
            'message': '股票資料更新已開始'
        })
        
    except Exception as e:
        is_updating = False
        logger.error(f"更新股票資料API錯誤: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '更新股票資料時發生錯誤'
        }), 500

@app.route('/api/stocks/screen', methods=['POST'])
def screen_stocks():
    """篩選股票API"""
    try:
        if initialization_error:
            return jsonify({
                'success': False,
                'error': '系統初始化失敗',
                'message': initialization_error,
                'data': []
            }), 500
        
        # 使用預設結果進行展示
        mock_results = [
            {
                'code': '2330',
                'name': '台積電',
                'close_price': 580.0,
                'change_percent': 1.5,
                'fund_trend': '流入',
                'multi_short_line': '多頭',
                'entry_score': 85
            },
            {
                'code': '2317',
                'name': '鴻海',
                'close_price': 105.0,
                'change_percent': 0.8,
                'fund_trend': '流入',
                'multi_short_line': '多頭',
                'entry_score': 78
            },
            {
                'code': '2454',
                'name': '聯發科',
                'close_price': 920.0,
                'change_percent': 2.1,
                'fund_trend': '流入',
                'multi_short_line': '多頭',
                'entry_score': 82
            }
        ]
        
        return jsonify({
            'success': True,
            'data': mock_results,
            'count': len(mock_results),
            'note': '展示模式 - 使用模擬資料'
        })
        
    except Exception as e:
        logger.error(f"篩選股票API錯誤: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '篩選股票時發生錯誤',
            'data': []
        }), 500

@app.route('/api/task/status')
def get_task_status():
    """獲取任務狀態"""
    return jsonify({
        'is_updating': is_updating,
        'last_update_time': last_update_time.isoformat() if last_update_time else None,
        'stocks_count': len(stocks_data),
        'initialization_error': initialization_error
    })

@app.route('/health')
def health_check():
    """健康檢查端點"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'taiwan-stock-screener',
        'initialization_status': 'failed' if initialization_error else 'success'
    })

@app.route('/version')
def version():
    """版本資訊"""
    return jsonify({
        'version': '1.0.1-fixed',
        'service': 'taiwan-stock-screener',
        'platform': 'render',
        'features': ['robust-initialization', 'fallback-data']
    })

@app.errorhandler(404)
def not_found(error):
    """404錯誤處理"""
    return jsonify({
        'success': False,
        'error': 'Not Found',
        'message': '請求的資源不存在'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """500錯誤處理"""
    return jsonify({
        'success': False,
        'error': 'Internal Server Error',
        'message': '伺服器內部錯誤'
    }), 500

@app.after_request
def after_request(response):
    """添加安全標頭"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

def keep_alive():
    """保持服務活躍，避免Render休眠"""
    app_url = os.environ.get('RENDER_EXTERNAL_URL')
    if not app_url:
        return
    
    while True:
        try:
            time.sleep(25 * 60)  # 每25分鐘ping一次
            requests.get(f"{app_url}/health", timeout=10)
            logger.info("Keep-alive ping sent")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")

if __name__ == '__main__':
    # 獲取環境變數
    PORT = int(os.environ.get('PORT', 10000))
    HOST = '0.0.0.0'
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info("台股主力資金進入篩選器啟動中...")
    
    # 嘗試初始化組件（不會因失敗而退出）
    initialization_success = safe_import_modules()
    
    if initialization_success:
        logger.info("組件初始化成功")
    else:
        logger.warning("組件初始化失敗，將以降級模式運行")
    
    # 啟動keep-alive線程（僅在Render環境）
    if os.environ.get('RENDER'):
        threading.Thread(target=keep_alive, daemon=True).start()
        logger.info("Keep-alive thread started")
    
    # 總是啟動應用（即使組件初始化失敗）
    logger.info(f"啟動台股主力資金進入篩選器，端口: {PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)

