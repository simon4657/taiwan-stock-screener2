#!/usr/bin/env python3
"""
台股主力資金進入篩選器 - 修正股票名稱顯示問題版本
"""

import os
import logging
import threading
import time
import json
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
stocks_data = {}
last_update_time = None
is_updating = False

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
        {'stock_id': '2308', 'stock_name': '台達電'},
        {'stock_id': '2409', 'stock_name': '友達'},
        {'stock_id': '3711', 'stock_name': '日月光投控'},
        {'stock_id': '2207', 'stock_name': '和泰車'},
        {'stock_id': '2105', 'stock_name': '正新'},
        {'stock_id': '1216', 'stock_name': '統一'}
    ]

def get_stock_name_by_code(stock_code):
    """根據股票代碼獲取股票名稱"""
    stock_list = get_default_stock_list()
    for stock in stock_list:
        if stock['stock_id'] == stock_code:
            return stock['stock_name']
    return f"股票{stock_code}"  # 如果找不到，返回預設名稱

def get_stock_web_data(stock_code, stock_name=None):
    """從網路獲取股票資料（修正Pine Script邏輯版）"""
    try:
        # 這裡可以實作真實的API調用
        # 目前使用模擬資料，但遵循修正的Pine Script邏輯
        import random
        
        base_price = random.uniform(50, 1000)
        
        # 確保包含股票名稱
        if not stock_name:
            stock_name = get_stock_name_by_code(stock_code)
        
        # 修正Pine Script的指標計算 - 更合理的邏輯
        fund_flow_trend = random.uniform(0, 100)  # 資金流向趨勢 (0-100)
        bull_bear_line = random.uniform(0, 100)   # 多空線 (0-100)
        
        # 修正主力進場信號邏輯
        # 1. 資金流向必須高於多空線 (真正的突破)
        is_fund_above_line = fund_flow_trend > bull_bear_line
        # 2. 多空線在超賣區域 (< 25)
        is_oversold = bull_bear_line < 25
        # 3. 主力進場信號 = 資金流向突破多空線且在超賣區
        banker_entry_signal = is_fund_above_line and is_oversold
        
        # 根據Pine Script邏輯判斷主力狀態和對應的股價表現
        if banker_entry_signal:
            fund_status = '主力進場'  # 黃色蠟燭
            entry_signal_strength = 95
            # 主力進場通常伴隨股價上漲 (合理的邏輯關聯)
            change_percent = random.uniform(1.0, 6.0)  # 上漲1-6%
        elif is_fund_above_line:
            fund_status = '主力增倉'  # 綠色蠟燭
            entry_signal_strength = 85
            # 主力增倉通常伴隨股價上漲或持平
            change_percent = random.uniform(-0.5, 4.0)  # -0.5%到4%
        elif fund_flow_trend < bull_bear_line:
            fund_status = '主力退場'  # 紅色蠟燭
            entry_signal_strength = 30
            # 主力退場通常伴隨股價下跌
            change_percent = random.uniform(-5.0, -0.5)  # 下跌0.5-5%
        else:
            fund_status = '主力觀望'  # 其他狀態
            entry_signal_strength = 50
            # 觀望狀態股價變化較小
            change_percent = random.uniform(-2.0, 2.0)  # -2%到2%
        
        # 轉換為原有格式以保持兼容性
        if fund_status == '主力進場' or fund_status == '主力增倉':
            fund_trend = '流入'
        elif fund_status == '主力退場':
            fund_trend = '流出'
        else:
            fund_trend = '持平'
        
        # 多空線狀態 (基於bull_bear_line數值)
        if bull_bear_line > 75:
            multi_short_line = '多頭'
        elif bull_bear_line < 25:
            multi_short_line = '空頭'
        else:
            multi_short_line = '盤整'
        
        return {
            'code': stock_code,
            'name': stock_name,  # 確保包含名稱
            'close_price': round(base_price, 2),
            'change_percent': round(change_percent, 2),
            'volume': random.randint(1000, 100000),
            'fund_trend': fund_trend,
            'multi_short_line': multi_short_line,
            'entry_score': entry_signal_strength,
            # Pine Script 特有指標
            'fund_flow_trend': round(fund_flow_trend, 2),
            'bull_bear_line': round(bull_bear_line, 2),
            'banker_entry_signal': banker_entry_signal,
            'fund_status': fund_status
        }
    except Exception as e:
        logger.error(f"獲取股票 {stock_code} 資料失敗: {e}")
        return None

@app.route('/')
def index():
    """主頁面"""
    return render_template('index.html')

@app.route('/api/stocks/list')
def get_stock_list():
    """獲取股票清單API"""
    try:
        stock_list = get_default_stock_list()
        return jsonify({
            'success': True,
            'data': stock_list,
            'count': len(stock_list)
        })
    except Exception as e:
        logger.error(f"獲取股票清單失敗: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': '獲取股票清單時發生錯誤'
        }), 500

@app.route('/api/stocks/update', methods=['POST'])
def update_stocks():
    """更新股票資料API"""
    global is_updating, last_update_time, stocks_data
    
    try:
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
                stock_list = get_default_stock_list()
                
                # 更新股票資料
                stocks_data = {}
                for stock in stock_list:
                    stock_code = stock['stock_id']
                    stock_name = stock['stock_name']
                    stock_data = get_stock_web_data(stock_code, stock_name)
                    if stock_data:
                        stocks_data[stock_code] = stock_data
                    
                    # 模擬處理時間
                    time.sleep(0.1)
                
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
        # 如果沒有資料，先生成一些
        if not stocks_data:
            stock_list = get_default_stock_list()
            for stock in stock_list:  # 處理所有股票
                stock_code = stock['stock_id']
                stock_name = stock['stock_name']
                stock_data = get_stock_web_data(stock_code, stock_name)
                if stock_data:
                    # 確保名稱正確設定
                    stock_data['name'] = stock_name
                    stocks_data[stock_code] = stock_data
        
        # 篩選主力進場股票 - 使用Pine Script邏輯
        results = []
        for code, data in stocks_data.items():
            # Pine Script主力進場條件檢查
            banker_entry_signal = data.get('banker_entry_signal', False)
            fund_flow_trend = data.get('fund_flow_trend', 0)
            bull_bear_line = data.get('bull_bear_line', 0)
            fund_status = data.get('fund_status', '主力觀望')
            
            # Pine Script的核心篩選條件
            # 1. 主力進場信號 (黃色蠟燭) - 最優先
            # 2. 主力增倉信號 (綠色蠟燭) - 次優先
            is_banker_entry = banker_entry_signal  # 資金流向突破多空線且在超賣區
            is_banker_increase = fund_flow_trend > bull_bear_line and not banker_entry_signal  # 資金流向高於多空線
            
            # 符合Pine Script主力進場或增倉條件
            if is_banker_entry or is_banker_increase:
                # 確保名稱欄位不為空
                stock_name = data.get('name', '')
                if not stock_name:
                    stock_name = get_stock_name_by_code(code)
                
                # 根據Pine Script邏輯計算優先級評分
                if is_banker_entry:
                    priority_score = 100  # 主力進場信號最高優先級
                    signal_type = '主力進場'
                else:
                    priority_score = 85   # 主力增倉信號次優先級
                    signal_type = '主力增倉'
                
                results.append({
                    'code': data.get('code', code),
                    'name': stock_name,  # 確保名稱不為空
                    'close_price': data.get('close_price', 0),
                    'change_percent': data.get('change_percent', 0),
                    'fund_trend': data.get('fund_trend', '持平'),
                    'multi_short_line': data.get('multi_short_line', '盤整'),
                    'entry_score': priority_score,
                    'signal_type': signal_type,
                    'fund_flow_trend': fund_flow_trend,
                    'bull_bear_line': bull_bear_line
                })
        
        # 按優先級評分排序 (主力進場信號優先)
        results.sort(key=lambda x: x.get('entry_score', 0), reverse=True)
        
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results),
            'note': f'篩選出 {len(results)} 支符合Pine Script主力進場條件的股票',
            'criteria': 'Pine Script邏輯：資金流向突破多空線(超賣區) 或 資金流向高於多空線'
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
        'initialization_status': 'success'
    })

@app.route('/health')
def health_check():
    """健康檢查端點"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'taiwan-stock-screener',
        'python_version': '3.13-compatible',
        'initialization_status': 'success',
        'version': 'fixed-names'
    })

@app.route('/version')
def version():
    """版本資訊"""
    return jsonify({
        'version': '1.0.3-fixed-names',
        'service': 'taiwan-stock-screener',
        'platform': 'render',
        'python_version': '3.13-compatible',
        'features': ['python313-compatible', 'no-pandas', 'no-lxml', 'fixed-stock-names']
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
    logger.info("Python 3.13兼容版本 - 修正股票名稱顯示")
    
    # 啟動keep-alive線程（僅在Render環境）
    if os.environ.get('RENDER'):
        threading.Thread(target=keep_alive, daemon=True).start()
        logger.info("Keep-alive thread started")
    
    # 啟動應用
    logger.info(f"啟動台股主力資金進入篩選器，端口: {PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)

