#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台股主力資金進入篩選器 - 上市市場版本

使用Pine Script技術分析邏輯，專門針對台灣上市市場股票進行主力資金進場信號篩選
"""

from flask import Flask, render_template, jsonify, request
import requests
import json
import math
from datetime import datetime, timedelta, timezone
import pytz
import logging
import traceback
from typing import Dict, List, Optional, Tuple, Any
import time
import urllib3

# 抑制SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 全域變數
stocks_data = {}
last_update_time = None
data_date = None

# 台灣時區
TW_TZ = pytz.timezone('Asia/Taipei')

def get_taiwan_time():
    """獲取台灣時間"""
    return datetime.now(TW_TZ)

def convert_roc_date_to_ad(roc_date_str):
    """將民國年日期轉換為西元年日期"""
    try:
        if not roc_date_str or len(roc_date_str) != 7:
            return None
        
        roc_year = int(roc_date_str[:3])
        month = int(roc_date_str[3:5])
        day = int(roc_date_str[5:7])
        
        ad_year = roc_year + 1911
        return f"{ad_year:04d}-{month:02d}-{day:02d}"
    except:
        return None

def convert_ad_date_to_roc(ad_date_str):
    """將西元年日期轉換為民國年日期"""
    try:
        if isinstance(ad_date_str, str):
            if '-' in ad_date_str:
                year, month, day = ad_date_str.split('-')
            else:
                year = ad_date_str[:4]
                month = ad_date_str[4:6]
                day = ad_date_str[6:8]
        else:
            return None
        
        roc_year = int(year) - 1911
        return f"{roc_year:03d}{int(month):02d}{int(day):02d}"
    except:
        return None

def fetch_otc_stock_data():
    """獲取上市股票資料（從TWSE API），含重試機制"""
    
    # 主要 API：台灣證券交易所
    primary_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'Cache-Control': 'no-cache',
        'Referer': 'https://www.twse.com.tw/'
    }
    
    # 重試機制：最多嘗試 3 次
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"開始獲取上市股票資料（第 {attempt + 1} 次嘗試）...")
            
            response = requests.get(
                primary_url,
                headers=headers,
                timeout=60,  # 增加超時時間至 60 秒
                verify=False
            )
            response.raise_for_status()
            
            data = response.json()
            
            if not data or len(data) == 0:
                logger.warning(f"第 {attempt + 1} 次嘗試：TWSE API 回傳空資料")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
            
            logger.info(f"成功獲取證交所資料，共 {len(data)} 筆記錄")
            return data
            
        except requests.exceptions.Timeout:
            logger.error(f"第 {attempt + 1} 次嘗試：證交所API請求超時")
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
        except requests.exceptions.ConnectionError as e:
            logger.error(f"第 {attempt + 1} 次嘗試：無法連接到證交所API: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
        except requests.exceptions.HTTPError as e:
            logger.error(f"第 {attempt + 1} 次嘗試：證交所API HTTP錯誤: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
        except Exception as e:
            logger.error(f"第 {attempt + 1} 次嘗試：獲取證交所資料時發生錯誤: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
    
    logger.error("所有重試均失敗，無法獲取 TWSE 資料")
    return None
def process_otc_stock_data(raw_data):
    """處理上市股票資料（從TWSE API）"""
    processed_stocks = {}
    current_date = None
    
    try:
        for item in raw_data:
            # 獲取股票基本資訊
            stock_code = item.get('Code', '').strip()
            stock_name = item.get('Name', '').strip()
            
            # 過濾條件：只處理上市股票（代碼1000-9999）
            if (stock_code and 
                len(stock_code) == 4 and 
                stock_code.isdigit() and
                1000 <= int(stock_code) <= 9999 and  # 限制為上市股票代碼範圍
                stock_name and
                not any(keyword in stock_name for keyword in ['DR', 'TDR', 'ETF', 'ETN', '權證', '特別股', '存託憑證'])):
                
                try:
                    # 安全的數值轉換函數
                    def safe_float(value, default=0.0):
                        try:
                            if value is None or value == '' or value == '-':
                                return default
                            return float(str(value).replace(',', ''))
                        except (ValueError, TypeError):
                            return default
                    
                    def safe_int(value, default=0):
                        try:
                            if value is None or value == '' or value == '-':
                                return default
                            return int(str(value).replace(',', ''))
                        except (ValueError, TypeError):
                            return default
                    
                    # 解析數值，處理可能的逗號分隔符和空值
                    opening_price = safe_float(item.get('OpeningPrice'))
                    highest_price = safe_float(item.get('HighestPrice'))
                    lowest_price = safe_float(item.get('LowestPrice'))
                    closing_price = safe_float(item.get('ClosingPrice'))
                    trade_volume = safe_int(item.get('TradeVolume'))
                    
                    # 過濾無效資料
                    if closing_price > 0 and trade_volume > 0:
                        # 計算漲跌幅
                        change = safe_float(item.get('Change'))
                        
                        # 計算漲跌幅百分比
                        change_percent = (change / (closing_price - change)) * 100 if (closing_price - change) != 0 else 0
                        
                        # 獲取交易日期 - 轉換民國年為西元年
                        trade_date_roc = item.get('Date', '')
                        if trade_date_roc and len(trade_date_roc) == 7:  # 1140829格式
                            try:
                                year = int(trade_date_roc[:3]) + 1911  # 民國年轉西元年
                                month = trade_date_roc[3:5]
                                day = trade_date_roc[5:7]
                                trade_date = f"{year}-{month}-{day}"
                            except:
                                trade_date = ''
                        else:
                            trade_date = ''
                        
                        if not current_date and trade_date:
                            current_date = trade_date
                        
                        processed_stocks[stock_code] = {
                            'code': stock_code,
                            'name': stock_name,
                            'close': closing_price,
                            'open': opening_price,
                            'high': highest_price,
                            'low': lowest_price,
                            'volume': trade_volume,
                            'date': trade_date,
                            'change': change,
                            'change_percent': change_percent,
                            'market': 'TWSE'  # 標記為上市市場
                        }
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"處理股票 {stock_code} 資料時發生錯誤: {e}")
                    continue
        
        logger.info(f"成功處理 {len(processed_stocks)} 支上市股票資料")
        return processed_stocks, current_date
        
    except Exception as e:
        logger.error(f"處理上市股票資料時發生錯誤: {str(e)}")
        return {}, None

def is_valid_otc_stock(stock_code, stock_name):
    """判斷是否為有效的上市一般股票"""
    if not stock_code or not stock_name:
        return False
    
    # 檢查股票代碼格式
    if not stock_code.isdigit() or len(stock_code) < 4:
        return False
    
    # 上市股票代碼範圍（一般為1000-9999）
    try:
        code_num = int(stock_code)
        if not (1000 <= code_num <= 9999):
            return False
    except ValueError:
        return False
    
    # 排除特殊股票類型
    exclude_suffixes = ['B', 'K', 'L', 'R', 'F']  # ETF、債券等
    if any(stock_code.endswith(suffix) for suffix in exclude_suffixes):
        return False
    
    # 排除特殊名稱
    exclude_keywords = ['ETF', 'ETN', '權證', '特別股', '存託憑證', '債券', 'REITs']
    if any(keyword in stock_name for keyword in exclude_keywords):
        return False
    
    return True

def calculate_weighted_simple_average(src_values, length, weight):
    """完全按照Pine Script邏輯實現的加權移動平均"""
    if not src_values or length <= 0:
        return 0
    
    if len(src_values) == 1:
        return src_values[0]
    
    # Pine Script狀態變量
    sum_float = 0.0
    output = None
    
    # 逐步計算，維護Pine Script的狀態邏輯
    for i, src in enumerate(src_values):
        # Pine Script邏輯：sum_float := nz(sum_float[1]) - nz(src[length]) + src
        if i >= length:
            # 移除length期前的值，加入當前值
            sum_float = sum_float - src_values[i - length] + src
        else:
            # 累加當前值
            sum_float += src
        
        # 計算移動平均
        if i >= length - 1:
            moving_average = sum_float / length
        else:
            moving_average = None  # Pine Script中會是na
        
        # Pine Script邏輯：output := na(output[1]) ? moving_average : (src * weight + output[1] * (length - weight)) / length
        if output is None:
            # 第一次計算或moving_average為None時
            output = moving_average if moving_average is not None else src
        else:
            if moving_average is not None:
                # 標準的加權計算
                output = (src * weight + output * (length - weight)) / length
            else:
                # 如果moving_average為None，保持原值
                output = (src * weight + output * (length - weight)) / length
    
    return output if output is not None else (src_values[-1] if src_values else 0)

def calculate_pine_script_indicators(ohlc_data):
    """完全按照Pine Script邏輯計算技術指標"""
    if len(ohlc_data) < 34:  # 需要足夠的歷史數據
        return None
    
    # 提取OHLC數據
    closes = [d['close'] for d in ohlc_data]
    highs = [d['high'] for d in ohlc_data]
    lows = [d['low'] for d in ohlc_data]
    opens = [d['open'] for d in ohlc_data]
    
    # 計算典型價格 (2 * close + high + low + open) / 5
    typical_prices = [(2 * c + h + l + o) / 5 for c, h, l, o in zip(closes, highs, lows, opens)]
    
    # 計算資金流向趨勢（完全按照Pine Script公式）
    fund_flow_values = []
    
    for i in range(len(closes)):
        # 計算27期最高最低價
        start_idx = max(0, i - 26)
        lowest_27 = min(lows[start_idx:i+1])
        highest_27 = max(highs[start_idx:i+1])
        
        if highest_27 != lowest_27:
            # 計算相對位置
            relative_pos = (closes[i] - lowest_27) / (highest_27 - lowest_27) * 100
            
            # 收集足夠的相對位置數據用於加權平均
            relative_positions = []
            for j in range(max(0, i - 4), i + 1):
                start_j = max(0, j - 26)
                low_27_j = min(lows[start_j:j+1])
                high_27_j = max(highs[start_j:j+1])
                if high_27_j != low_27_j:
                    rel_pos_j = (closes[j] - low_27_j) / (high_27_j - low_27_j) * 100
                else:
                    rel_pos_j = 50
                relative_positions.append(rel_pos_j)
            
            # 第一層加權簡單平均（5期，權重1）
            wsa1 = calculate_weighted_simple_average(relative_positions, min(5, len(relative_positions)), 1)
            
            # 第二層加權簡單平均（3期，權重1）
            if i >= 2:
                # 收集前面的wsa1值
                wsa1_values = []
                for k in range(max(0, i - 2), i + 1):
                    # 重新計算每個時點的wsa1
                    rel_pos_k = []
                    for j in range(max(0, k - 4), k + 1):
                        start_j = max(0, j - 26)
                        low_27_j = min(lows[start_j:j+1])
                        high_27_j = max(highs[start_j:j+1])
                        if high_27_j != low_27_j:
                            rel_pos_j = (closes[j] - low_27_j) / (high_27_j - low_27_j) * 100
                        else:
                            rel_pos_j = 50
                        rel_pos_k.append(rel_pos_j)
                    
                    wsa1_k = calculate_weighted_simple_average(rel_pos_k, min(5, len(rel_pos_k)), 1)
                    wsa1_values.append(wsa1_k)
                
                wsa2 = calculate_weighted_simple_average(wsa1_values, min(3, len(wsa1_values)), 1)
            else:
                wsa2 = wsa1
            
            # 最終公式：(3 * wsa1 - 2 * wsa2 - 50) * 1.032 + 50
            fund_flow = (3 * wsa1 - 2 * wsa2 - 50) * 1.032 + 50
        else:
            fund_flow = 50
        
        fund_flow_values.append(max(0, min(100, fund_flow)))
    
    # 計算多空線（13期EMA）
    # 先計算標準化的典型價格
    bull_bear_values = []
    for i in range(len(typical_prices)):
        # 計算34期最高最低價
        start_idx = max(0, i - 33)
        lowest_34 = min(lows[start_idx:i+1])
        highest_34 = max(highs[start_idx:i+1])
        
        if highest_34 != lowest_34:
            normalized_price = (typical_prices[i] - lowest_34) / (highest_34 - lowest_34) * 100
        else:
            normalized_price = 50
        bull_bear_values.append(max(0, min(100, normalized_price)))
    
    # 計算13期EMA
    bull_bear_line_values = []
    for i in range(len(bull_bear_values)):
        if i < 13:
            ema_value = sum(bull_bear_values[:i+1]) / (i+1)
        else:
            ema_value = calculate_ema(bull_bear_values[:i+1], 13)
        bull_bear_line_values.append(ema_value)
    
    # 檢查當日和前一日的黃柱信號
    current_day_signal = False
    previous_day_signal = False
    
    if len(fund_flow_values) >= 2 and len(bull_bear_line_values) >= 2:
        # 檢查當日黃柱
        current_fund = fund_flow_values[-1]
        previous_fund = fund_flow_values[-2]
        current_bull_bear = bull_bear_line_values[-1]
        previous_bull_bear = bull_bear_line_values[-2]
        
        # Pine Script crossover邏輯：ta.crossover(fund_flow_trend, bull_bear_line)
        is_crossover_today = (current_fund > current_bull_bear) and (previous_fund <= previous_bull_bear)
        is_oversold_today = current_bull_bear < 25
        current_day_signal = is_crossover_today and is_oversold_today
        
        # 檢查前一日黃柱
        if len(fund_flow_values) >= 3 and len(bull_bear_line_values) >= 3:
            prev_fund = fund_flow_values[-2]
            prev_prev_fund = fund_flow_values[-3]
            prev_bull_bear = bull_bear_line_values[-2]
            prev_prev_bull_bear = bull_bear_line_values[-3]
            
            is_crossover_yesterday = (prev_fund > prev_bull_bear) and (prev_prev_fund <= prev_prev_bull_bear)
            is_oversold_yesterday = prev_bull_bear < 25
            previous_day_signal = is_crossover_yesterday and is_oversold_yesterday
        
        # 黃柱信號：當日或前一日出現
        banker_entry_signal = current_day_signal or previous_day_signal
        
        # 記錄詳細計算結果用於調試（僅記錄符合條件的股票）
        if banker_entry_signal:
            logger.info(f"🟡 發現黃柱信號:")
            logger.info(f"  當日: 資金流向={current_fund:.2f}, 多空線={current_bull_bear:.2f}, crossover={is_crossover_today}, 超賣={is_oversold_today}, 黃柱={current_day_signal}")
            if len(fund_flow_values) >= 3:
                logger.info(f"  前日: 資金流向={prev_fund:.2f}, 多空線={prev_bull_bear:.2f}, crossover={is_crossover_yesterday}, 超賣={is_oversold_yesterday}, 黃柱={previous_day_signal}")
        
        return {
            'fund_trend': current_fund,
            'multi_short_line': current_bull_bear,
            'banker_entry_signal': banker_entry_signal,
            'is_crossover': (is_crossover_today if current_day_signal else is_crossover_yesterday),
            'is_oversold': (is_oversold_today if current_day_signal else is_oversold_yesterday),
            'fund_trend_previous': previous_fund if len(fund_flow_values) >= 2 else current_fund,
            'multi_short_line_previous': previous_bull_bear if len(bull_bear_line_values) >= 2 else current_bull_bear
        }
    
    return None

def calculate_ema(values, period):
    """計算指數移動平均"""
    if len(values) < period:
        return sum(values) / len(values) if values else 0
    
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period  # 初始SMA
    
    for value in values[period:]:
        ema = (value * multiplier) + (ema * (1 - multiplier))
    
    return ema

def update_stocks_data():
    """更新股票資料"""
    global stocks_data, last_update_time, data_date
    
    try:
        logger.info("開始更新上市股票資料...")
        
        # 獲取上市股票資料
        raw_data = fetch_otc_stock_data()
        if not raw_data:
            logger.error("無法獲取上市股票資料")
            return False
        
        # 處理資料
        processed_data, current_date = process_otc_stock_data(raw_data)
        if not processed_data:
            logger.error("處理上市股票資料失敗")
            return False
        
        # 更新全域變數
        stocks_data = processed_data
        data_date = current_date
        last_update_time = get_taiwan_time()
        
        logger.info(f"成功更新 {len(stocks_data)} 支上市股票資料，資料日期: {data_date}")
        return True
        
    except Exception as e:
        logger.error(f"更新上市股票資料時發生錯誤: {str(e)}")
        return False

@app.route('/')
def index():
    """首頁"""
    return render_template('index.html')

@app.route('/api/diagnose')
def diagnose():
    """診斷端點：測試 TWSE API 連線狀況"""
    import time as time_module
    result = {
        'timestamp': get_taiwan_time().strftime('%Y-%m-%d %H:%M:%S'),
        'tests': {}
    }
    
    # 測試 TWSE API 連線
    try:
        start = time_module.time()
        url = 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Referer': 'https://www.twse.com.tw/'
        }
        response = requests.get(url, headers=headers, timeout=60, verify=False)
        elapsed = time_module.time() - start
        
        content_type = response.headers.get('Content-Type', 'unknown')
        raw_preview = repr(response.text[:200]) if response.text else '(empty)'
        
        try:
            json_data = response.json()
            result['tests']['twse_api'] = {
                'status': 'success',
                'http_code': response.status_code,
                'elapsed_seconds': round(elapsed, 2),
                'content_type': content_type,
                'records_count': len(json_data)
            }
        except Exception as json_err:
            result['tests']['twse_api'] = {
                'status': 'json_parse_failed',
                'http_code': response.status_code,
                'elapsed_seconds': round(elapsed, 2),
                'content_type': content_type,
                'json_error': str(json_err),
                'raw_preview': raw_preview
            }
    except Exception as e:
        result['tests']['twse_api'] = {
            'status': 'failed',
            'error': str(e),
            'error_type': type(e).__name__
        }
    
    # 測試 DNS 解析
    try:
        import socket
        ip = socket.gethostbyname('openapi.twse.com.tw')
        result['tests']['dns_resolution'] = {
            'status': 'success',
            'ip': ip
        }
    except Exception as e:
        result['tests']['dns_resolution'] = {
            'status': 'failed',
            'error': str(e)
        }
    
    # 目前股票資料狀態
    result['stocks_data_count'] = len(stocks_data)
    result['data_date'] = data_date
    result['last_update'] = last_update_time.strftime('%Y-%m-%d %H:%M:%S') if last_update_time else None
    
    return jsonify(result)

@app.route('/api/health')
def health_check():
    """健康檢查API"""
    try:
        taiwan_time = get_taiwan_time()
        
        # 確保時間格式正確
        last_update_str = None
        if last_update_time:
            last_update_str = last_update_time.strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'status': 'healthy',
            'timestamp': taiwan_time.strftime('%Y-%m-%d %H:%M:%S'),
            'stocks_count': len(stocks_data),
            'data_date': data_date,
            'last_update': last_update_str,
            'market': 'TWSE',  # 標記為上市市場
            'version': '4.0 - TWSE Market Edition'
        })
    except Exception as e:
        logger.error(f"健康檢查失敗: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/update', methods=['POST'])
def update_data():
    """更新股票資料API"""
    try:
        if update_stocks_data():
            # 確保時間格式正確
            update_time_str = None
            if last_update_time:
                update_time_str = last_update_time.strftime('%Y-%m-%d %H:%M:%S')
            
            return jsonify({
                'success': True,
                'message': f'成功更新 {len(stocks_data)} 支上市股票資料',
                'stocks_count': len(stocks_data),
                'data_date': data_date,
                'update_time': update_time_str,
                'market': 'TWSE'
            })
        else:
            return jsonify({
                'success': False,
                'message': '更新失敗，請稍後再試'
            }), 500
    except Exception as e:
        logger.error(f"更新API錯誤: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'更新失敗: {str(e)}'
        }), 500

@app.route('/api/stocks')
def get_stocks():
    """獲取股票清單API"""
    try:
        # 返回前50支股票作為預覽
        preview_stocks = dict(list(stocks_data.items())[:50])
        
        return jsonify({
            'stocks': preview_stocks,
            'total_count': len(stocks_data),
            'preview_count': len(preview_stocks),
            'data_date': data_date,
            'market': 'TWSE'
        })
        
    except Exception as e:
        logger.error(f"獲取股票清單失敗: {str(e)}")
        return jsonify({'error': str(e)}), 500

def format_volume(volume):
    """格式化成交張數顯示（1張=1000股）"""
    # 將成交量（股）轉換為成交張數（張）
    volume_lots = volume / 1000
    
    if volume_lots >= 100000:  # 10萬張以上
        return f"{volume_lots / 10000:.1f}萬張"
    elif volume_lots >= 1000:  # 1千張以上
        return f"{volume_lots / 1000:.1f}千張"
    else:
        return f"{volume_lots:,.0f}張"

def calculate_trend_direction(current_value, previous_value, threshold=0.05):
    """計算趨勢方向和變化百分比"""
    if previous_value == 0:
        return "→", 0
    
    change_percent = ((current_value - previous_value) / previous_value) * 100
    
    if change_percent > threshold * 100:
        return "↑", change_percent
    elif change_percent < -threshold * 100:
        return "↓", change_percent
    else:
        return "→", change_percent

def calculate_volume_ratio(current_volume, historical_volumes):
    """計算量比（當日成交量/近5日平均成交量）"""
    if not historical_volumes or len(historical_volumes) == 0:
        return 1.0
    
    avg_volume = sum(historical_volumes) / len(historical_volumes)
    if avg_volume == 0:
        return 1.0
    
    return current_volume / avg_volume

def get_volume_ratio_class(volume_ratio):
    """根據量比獲取CSS類別"""
    if volume_ratio >= 2.0:
        return "volume-extreme"  # 異常放量（紅色粗體）
    elif volume_ratio >= 1.5:
        return "volume-high"     # 明顯放量（橙色）
    elif volume_ratio >= 0.8:
        return "volume-normal"   # 正常（黑色）
    else:
        return "volume-low"      # 縮量（灰色）

def fetch_historical_data_for_indicators(stock_code, days=60):
    """獲取歷史資料用於技術指標計算（上市股票版本，Yahoo Finance為主）"""
    
    # 使用Yahoo Finance API獲取歷史數據
    try:
        logger.info(f"正在獲取 {stock_code} 歷史資料（Yahoo Finance API）...")
        
        import requests
        
        # Yahoo Finance API URL
        symbol = f"{stock_code}.TW"  # 上市股票使用.TW後綴
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Referer': 'https://finance.yahoo.com/'
        }
        
        params = {
            'range': '3mo',
            'interval': '1d',
            'includeAdjustedClose': 'true'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=20, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            
            if (data and 'chart' in data and 'result' in data['chart'] and 
                data['chart']['result'] and len(data['chart']['result']) > 0):
                
                result = data['chart']['result'][0]
                
                # 檢查數據結構
                if 'timestamp' not in result or 'indicators' not in result:
                    logger.warning(f"⚠️ {stock_code}: Yahoo Finance返回數據結構不完整")
                    return None
                
                timestamps = result['timestamp']
                quotes = result['indicators']['quote'][0]
                
                ohlc_data = []
                for i in range(len(timestamps)):
                    try:
                        if (quotes['open'][i] is not None and 
                            quotes['high'][i] is not None and 
                            quotes['low'][i] is not None and 
                            quotes['close'][i] is not None):
                            
                            ohlc_data.append({
                                'date': datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d'),
                                'open': float(quotes['open'][i]),
                                'high': float(quotes['high'][i]),
                                'low': float(quotes['low'][i]),
                                'close': float(quotes['close'][i]),
                                'volume': int(quotes['volume'][i]) if quotes['volume'][i] else 0
                            })
                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"⚠️ {stock_code}: 跳過無效數據點 {i}: {e}")
                        continue
                
                if len(ohlc_data) >= 34:
                    logger.info(f"✅ {stock_code}: 成功獲取 {len(ohlc_data)} 天歷史資料（Yahoo Finance）")
                    return ohlc_data[-days:] if len(ohlc_data) > days else ohlc_data
                else:
                    logger.warning(f"⚠️ {stock_code}: Yahoo Finance資料不足，僅 {len(ohlc_data)} 天（需要至少34天）")
                    return None
        
        logger.warning(f"❌ {stock_code}: Yahoo Finance失敗，HTTP狀態碼: {response.status_code}")
        if response.status_code == 404:
            logger.info(f"💡 {stock_code}: 可能是無效的股票代碼或該股票未在Yahoo Finance上市")
        
    except requests.exceptions.Timeout:
        logger.warning(f"❌ {stock_code}: Yahoo Finance請求超時")
    except requests.exceptions.ConnectionError:
        logger.warning(f"❌ {stock_code}: Yahoo Finance連接錯誤")
    except Exception as e:
        logger.warning(f"❌ {stock_code}: Yahoo Finance異常 - {e}")
    
    # 如果Yahoo Finance失敗，記錄錯誤並返回None
    logger.error(f"❌ {stock_code}: 無法獲取歷史資料")
    logger.info(f"💡 建議：請檢查網路連接、股票代碼是否正確，或稍後重試")
    
    return None

def get_stock_web_data(stock_code, stock_name=None):
    """獲取單支股票的完整資料（包含技術指標）"""
    try:
        # 獲取即時資料
        if stock_code not in stocks_data:
            logger.warning(f"股票 {stock_code} 沒有即時資料")
            return None
        
        current_data = stocks_data[stock_code]
        
        # 獲取歷史資料用於技術指標計算
        historical_data = fetch_historical_data_for_indicators(stock_code)
        
        if historical_data and len(historical_data) >= 34:
            # 將當日資料加入歷史資料
            today_data = {
                'date': convert_roc_date_to_ad(data_date) if data_date else current_data['date'],
                'open': current_data['open'],
                'high': current_data['high'],
                'low': current_data['low'],
                'close': current_data['close'],
                'volume': current_data['volume']
            }
            
            # 檢查是否已經包含當日資料
            if not historical_data or historical_data[-1]['date'] != today_data['date']:
                historical_data.append(today_data)
            
            # 計算Pine Script技術指標
            result = calculate_pine_script_indicators(historical_data)
            
            if result:
                fund_flow_trend = result['fund_trend']
                bull_bear_line = result['multi_short_line']
                banker_entry_signal = result['banker_entry_signal']
                is_crossover = result['is_crossover']
                is_oversold = result['is_oversold']
                fund_trend_previous = result['fund_trend_previous']
                multi_short_line_previous = result['multi_short_line_previous']
            
            if fund_flow_trend is not None:
                # 根據嚴格的Pine Script條件判斷狀態
                if banker_entry_signal:
                    signal_status = "🟡 黃柱信號"
                    score = 100
                elif is_crossover and not is_oversold:
                    signal_status = "突破但非超賣"
                    score = 75
                elif is_oversold and not is_crossover:
                    signal_status = "超賣但未突破"
                    score = 65
                elif fund_flow_trend > bull_bear_line:
                    signal_status = "資金流向強勢"
                    score = 55
                else:
                    signal_status = "資金流向弱勢"
                    score = 30
                
                # 計算成交量和趨勢信息
                current_volume = current_data['volume']
                volume_formatted = format_volume(current_volume)
                
                # 計算成交量趨勢（需要歷史成交量數據）
                historical_volumes = [d.get('volume', 0) for d in historical_data[-6:-1]] if len(historical_data) > 5 else []
                previous_volume = historical_volumes[-1] if historical_volumes else current_volume
                volume_trend, volume_change_percent = calculate_trend_direction(current_volume, previous_volume)
                
                # 計算量比
                volume_ratio = calculate_volume_ratio(current_volume, historical_volumes)
                volume_ratio_class = get_volume_ratio_class(volume_ratio)
                
                # 計算資金流向和多空線趨勢
                fund_trend_direction, fund_trend_change = calculate_trend_direction(fund_flow_trend, fund_trend_previous)
                multi_short_line_direction, multi_short_line_change = calculate_trend_direction(bull_bear_line, multi_short_line_previous)
                
                return {
                    'name': stock_name or current_data['name'],
                    'price': current_data['close'],
                    'change_percent': current_data['change_percent'],
                    'volume': current_volume,
                    'volume_formatted': volume_formatted,
                    'volume_trend': volume_trend,
                    'volume_change_percent': volume_change_percent,
                    'volume_ratio': volume_ratio,
                    'volume_ratio_class': volume_ratio_class,
                    'fund_trend': f"{fund_flow_trend:.2f}",
                    'fund_trend_direction': fund_trend_direction,
                    'fund_trend_change': fund_trend_change,
                    'multi_short_line': f"{bull_bear_line:.2f}",
                    'multi_short_line_direction': multi_short_line_direction,
                    'multi_short_line_change': multi_short_line_change,
                    'signal_status': signal_status,
                    'score': score,
                    'date': data_date,  # 使用統一的資料日期顯示格式
                    'is_crossover': is_crossover,
                    'is_oversold': is_oversold,
                    'banker_entry_signal': banker_entry_signal
                }
        
        # 如果無法計算技術指標，返回詳細錯誤資訊
        error_msg = "歷史資料獲取失敗"
        if historical_data is None:
            error_msg = "API連接失敗"
        elif len(historical_data) < 34:
            error_msg = f"資料不足({len(historical_data)}/34天)"
        
        logger.warning(f"股票 {stock_code} 無法計算技術指標: {error_msg}")
        
        # 即使無法計算技術指標，也要返回基本的成交量信息
        current_volume = current_data['volume']
        volume_formatted = format_volume(current_volume)
        
        return {
            'name': stock_name or current_data['name'],
            'price': current_data['close'],
            'change_percent': current_data['change_percent'],
            'volume': current_volume,
            'volume_formatted': volume_formatted,
            'volume_trend': 'flat',
            'volume_change_percent': 0,
            'volume_ratio': 1.0,
            'volume_ratio_class': 'volume-normal',
            'fund_trend': error_msg,
            'fund_trend_direction': 'flat',
            'fund_trend_change': 0,
            'multi_short_line': error_msg,
            'multi_short_line_direction': 'flat',
            'multi_short_line_change': 0,
            'signal_status': error_msg,
            'score': 0,
            'date': data_date,  # 使用統一的資料日期顯示格式
            'is_crossover': False,
            'is_oversold': False,
            'banker_entry_signal': False
        }
        
    except Exception as e:
        logger.error(f"獲取股票 {stock_code} 資料時發生錯誤: {e}")
        return None

@app.route('/api/screen', methods=['POST'])
def screen_stocks():
    """篩選股票"""
    try:
        current_time = get_taiwan_time()
        
        # 檢查是否有股票資料
        if not stocks_data:
            return jsonify({
                'success': False,
                'error': '請先更新上市股票資料'
            }), 400
        
        # 獲取所有股票的完整資料（全部股票分析）
        all_stocks_data = []
        total_stocks = len(stocks_data)
        processed_count = 0
        
        logger.info(f"開始分析 {total_stocks} 支上市股票的Pine Script指標...")
        
        # 分批處理以避免超時（減少批次大小）
        batch_size = 10  # 從50減少到10支股票每批
        stock_codes = list(stocks_data.keys())
        
        # 限制總處理數量以避免超時
        max_stocks = min(1044, len(stock_codes))  # 最多處理1044支上市股票
        stock_codes = stock_codes[:max_stocks]
        
        logger.info(f"為確保穩定性，本次處理前 {max_stocks} 支上市股票")
        
        for i in range(0, len(stock_codes), batch_size):
            batch_codes = stock_codes[i:i+batch_size]
            logger.info(f"處理第 {i//batch_size + 1} 批股票 ({len(batch_codes)} 支)...")
            
            for stock_code in batch_codes:
                try:
                    # 使用簡單的超時機制，不依賴signal
                    import time
                    start_time = time.time()
                    
                    stock_data = get_stock_web_data(stock_code)
                    
                    # 檢查是否超時
                    if time.time() - start_time > 10:  # 10秒超時
                        logger.warning(f"股票 {stock_code} 處理超時，跳過")
                        continue                
                    if stock_data:
                        all_stocks_data.append({
                            'code': stock_code,
                            **stock_data
                        })
                        processed_count += 1
                        
                        # 每處理5支股票記錄一次進度
                        if processed_count % 5 == 0:
                            logger.info(f"已處理 {processed_count}/{max_stocks} 支股票...")
                            
                except Exception as e:
                    logger.warning(f"處理股票 {stock_code} 時發生錯誤: {e}")
                    continue
        
        # 篩選出黃柱信號的股票
        yellow_candle_stocks = [stock for stock in all_stocks_data if stock.get('banker_entry_signal', False)]
        
        logger.info(f"篩選完成：共分析 {processed_count} 支上市股票，發現 {len(yellow_candle_stocks)} 支黃柱信號股票")
        
        # 按評分排序
        all_stocks_data.sort(key=lambda x: x.get('score', 0), reverse=True)
        yellow_candle_stocks.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        return jsonify({
            'success': True,
            'all_stocks': all_stocks_data,
            'yellow_candle_stocks': yellow_candle_stocks,
            'total_analyzed': processed_count,
            'yellow_candle_count': len(yellow_candle_stocks),
            'query_time': current_time.isoformat(),
            'data_date': data_date,
            'market': 'TWSE'
        })
        
    except Exception as e:
        logger.error(f"篩選上市股票時發生錯誤: {e}")
        return jsonify({
            'success': False,
            'error': f'篩選失敗: {str(e)}'
        }), 500

if __name__ == '__main__':
    # 啟動Flask應用（移除啟動時數據更新以避免部署超時）
    logger.info("台股主力資金篩選器 - 上市市場版本啟動中...")
    logger.info("💡 請使用 /update 端點手動更新股票數據")
    
    # 啟動Flask應用
    app.run(host='0.0.0.0', port=5000, debug=False)

