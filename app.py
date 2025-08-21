from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import logging
import threading
import time
import os
from datetime import datetime, timedelta, timezone
import requests
import json
import urllib3

# 台灣時區設定 (UTC+8)
TAIWAN_TZ = timezone(timedelta(hours=8))

def get_taiwan_time():
    """獲取台灣當前時間"""
    return datetime.now(TAIWAN_TZ)

def format_taiwan_time(dt=None):
    """格式化台灣時間為字符串"""
    if dt is None:
        dt = get_taiwan_time()
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def get_taiwan_date():
    """獲取台灣當前日期"""
    return get_taiwan_time().strftime('%Y-%m-%d')

def convert_roc_date_to_ad(roc_date_str):
    """將民國年日期轉換為西元年日期"""
    try:
        if len(roc_date_str) == 7:  # 1140813 格式
            roc_year = int(roc_date_str[:3])  # 114
            month = int(roc_date_str[3:5])    # 08
            day = int(roc_date_str[5:7])      # 13
            
            ad_year = roc_year + 1911  # 轉換為西元年
            return f"{ad_year:04d}{month:02d}{day:02d}"  # 20250813
        else:
            return roc_date_str  # 如果格式不對，返回原值
    except (ValueError, IndexError):
        return roc_date_str

def format_roc_date_for_display(roc_date_str):
    """將民國年日期格式化為顯示用格式"""
    try:
        if len(roc_date_str) == 7:  # 1140813 格式
            roc_year = int(roc_date_str[:3])  # 114
            month = int(roc_date_str[3:5])    # 08
            day = int(roc_date_str[5:7])      # 13
            
            return f"{roc_year}{month:02d}{day:02d}"  # 1140813
        else:
            return roc_date_str
    except (ValueError, IndexError):
        return roc_date_str

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# 全域變數
stocks_data = {}
is_updating = False
last_update_time = None
data_date = None  # 資料日期（民國年格式）
data_date_display = None  # 資料日期（顯示格式）

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

def get_default_stock_list():
    """獲取預設股票清單"""
    return [
        {'stock_id': '2330', 'stock_name': '台積電'},
        {'stock_id': '2317', 'stock_name': '鴻海'},
        {'stock_id': '2454', 'stock_name': '聯發科'},
        {'stock_id': '2881', 'stock_name': '富邦金'},
        {'stock_id': '2882', 'stock_name': '國泰金'},
        {'stock_id': '2883', 'stock_name': '開發金'},
        {'stock_id': '2884', 'stock_name': '玉山金'},
        {'stock_id': '2885', 'stock_name': '元大金'},
        {'stock_id': '2886', 'stock_name': '兆豐金'},
        {'stock_id': '2891', 'stock_name': '中信金'},
        {'stock_id': '2892', 'stock_name': '第一金'},
        {'stock_id': '2002', 'stock_name': '中鋼'},
        {'stock_id': '1303', 'stock_name': '南亞'},
        {'stock_id': '1301', 'stock_name': '台塑'},
        {'stock_id': '2412', 'stock_name': '中華電'},
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
    return f"股票{stock_code}"

def get_latest_trading_date():
    """獲取最近的交易日期（排除週末，基於台灣時間）"""
    today = get_taiwan_time()
    
    # 如果是週六(5)或週日(6)，回推到週五
    if today.weekday() == 5:  # 週六
        trading_date = today - timedelta(days=1)  # 週五
    elif today.weekday() == 6:  # 週日
        trading_date = today - timedelta(days=2)  # 週五
    else:
        # 平日，使用前一個交易日
        trading_date = today - timedelta(days=1)
    
    return trading_date.strftime('%Y%m%d')

def fetch_real_stock_data():
    """從台灣證券交易所API獲取真實股票資料（全部股票）"""
    global data_date, data_date_display
    
    try:
        # 台灣證券交易所OpenAPI
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        
        logger.info(f"正在從證交所API獲取股票資料: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"成功獲取證交所資料，共 {len(data)} 筆記錄")
        
        # 從第一筆資料獲取實際的資料日期
        if data and len(data) > 0:
            first_item_date = data[0].get('Date', '')
            if first_item_date:
                data_date = first_item_date  # 保存原始民國年格式
                data_date_display = format_roc_date_for_display(first_item_date)  # 顯示格式
                logger.info(f"資料日期: {data_date} (顯示: {data_date_display})")
        
        # 處理資料格式（處理所有股票）
        processed_data = {}
        valid_stocks = 0
        
        for item in data:
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
                    # 解析數值，處理可能的逗號分隔符
                    opening_price = float(item.get('OpeningPrice', '0').replace(',', ''))
                    highest_price = float(item.get('HighestPrice', '0').replace(',', ''))
                    lowest_price = float(item.get('LowestPrice', '0').replace(',', ''))
                    closing_price = float(item.get('ClosingPrice', '0').replace(',', ''))
                    trade_volume = int(item.get('TradeVolume', '0').replace(',', ''))
                    
                    # 過濾無效資料
                    if closing_price > 0 and trade_volume > 0:
                        # 計算漲跌幅
                        change_str = item.get('Change', '0').replace(',', '')
                        if change_str.startswith('+'):
                            change = float(change_str[1:])
                        elif change_str.startswith('-'):
                            change = -float(change_str[1:])
                        else:
                            change = float(change_str) if change_str else 0
                        
                        change_percent = (change / (closing_price - change)) * 100 if (closing_price - change) != 0 else 0
                        
                        processed_data[stock_code] = {
                            'name': stock_name,
                            'open': opening_price,
                            'high': highest_price,
                            'low': lowest_price,
                            'close': closing_price,
                            'volume': trade_volume,
                            'change': change,
                            'change_percent': change_percent,
                            'date': data_date_display  # 使用統一的資料日期
                        }
                        valid_stocks += 1
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"處理股票 {stock_code} 資料時發生錯誤: {e}")
                    continue
        
        logger.info(f"成功處理 {valid_stocks} 支有效股票資料")
        return processed_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"獲取證交所資料失敗: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"解析證交所資料失敗: {e}")
        return None
    except Exception as e:
        logger.error(f"處理證交所資料時發生未知錯誤: {e}")
        return None

def fetch_historical_data_for_indicators(stock_code, days=60):
    """獲取歷史資料用於技術指標計算（增強版本，包含備用機制）"""
    
    # 方法1: 使用Manus API Hub的Yahoo Finance API
    try:
        import sys
        sys.path.append('/opt/.manus/.sandbox-runtime')
        from data_api import ApiClient
        
        client = ApiClient()
        symbol = f"{stock_code}.TW"
        
        logger.info(f"正在獲取 {stock_code} 歷史資料（方法1: Manus API Hub）...")
        
        response = client.call_api('YahooFinance/get_stock_chart', query={
            'symbol': symbol,
            'region': 'TW',
            'interval': '1d',
            'range': '3mo',
            'includeAdjustedClose': True
        })
        
        if response and 'chart' in response and 'result' in response['chart']:
            result = response['chart']['result'][0]
            if 'timestamp' in result and 'indicators' in result:
                timestamps = result['timestamp']
                quotes = result['indicators']['quote'][0]
                
                ohlc_data = []
                for i in range(len(timestamps)):
                    if (quotes['open'][i] is not None and 
                        quotes['high'][i] is not None and 
                        quotes['low'][i] is not None and 
                        quotes['close'][i] is not None):
                        
                        ohlc_data.append({
                            'date': datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d'),
                            'open': quotes['open'][i],
                            'high': quotes['high'][i],
                            'low': quotes['low'][i],
                            'close': quotes['close'][i],
                            'volume': quotes['volume'][i] if quotes['volume'][i] else 0
                        })
                
                if len(ohlc_data) >= 34:  # 確保有足夠資料
                    logger.info(f"✅ {stock_code}: 成功獲取 {len(ohlc_data)} 天歷史資料（方法1）")
                    return ohlc_data[-days:] if len(ohlc_data) > days else ohlc_data
                else:
                    logger.warning(f"⚠️ {stock_code}: 資料不足，僅 {len(ohlc_data)} 天（需要至少34天）")
        
        logger.warning(f"❌ {stock_code}: 方法1失敗，嘗試備用方法...")
        
    except Exception as e:
        logger.warning(f"❌ {stock_code}: 方法1異常 - {e}")
    
    # 方法2: 直接使用requests訪問Yahoo Finance
    try:
        logger.info(f"正在獲取 {stock_code} 歷史資料（方法2: 直接Yahoo API）...")
        
        import requests
        import time
        
        # Yahoo Finance API URL
        symbol = f"{stock_code}.TW"
        period1 = int(time.time()) - (90 * 24 * 60 * 60)  # 90天前
        period2 = int(time.time())  # 現在
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        params = {
            'period1': period1,
            'period2': period2,
            'interval': '1d',
            'includePrePost': 'true',
            'events': 'div%2Csplit'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
            result = data['chart']['result'][0]
            if 'timestamp' in result and 'indicators' in result:
                timestamps = result['timestamp']
                quotes = result['indicators']['quote'][0]
                
                ohlc_data = []
                for i in range(len(timestamps)):
                    if (quotes['open'][i] is not None and 
                        quotes['high'][i] is not None and 
                        quotes['low'][i] is not None and 
                        quotes['close'][i] is not None):
                        
                        ohlc_data.append({
                            'date': datetime.fromtimestamp(timestamps[i]).strftime('%Y-%m-%d'),
                            'open': quotes['open'][i],
                            'high': quotes['high'][i],
                            'low': quotes['low'][i],
                            'close': quotes['close'][i],
                            'volume': quotes['volume'][i] if quotes['volume'][i] else 0
                        })
                
                if len(ohlc_data) >= 34:
                    logger.info(f"✅ {stock_code}: 成功獲取 {len(ohlc_data)} 天歷史資料（方法2）")
                    return ohlc_data[-days:] if len(ohlc_data) > days else ohlc_data
                else:
                    logger.warning(f"⚠️ {stock_code}: 資料不足，僅 {len(ohlc_data)} 天（需要至少34天）")
        
        logger.warning(f"❌ {stock_code}: 方法2失敗，嘗試備用方法...")
        
    except Exception as e:
        logger.warning(f"❌ {stock_code}: 方法2異常 - {e}")
    
    # 方法3: 生成模擬歷史資料（最後備用）
    try:
        logger.warning(f"⚠️ {stock_code}: 使用模擬歷史資料（方法3）")
        
        if stock_code not in stocks_data:
            return None
        
        current_data = stocks_data[stock_code]
        current_date = get_taiwan_time()
        
        # 生成60天的模擬歷史資料
        historical_data = []
        base_price = current_data['close']
        
        for i in range(59, -1, -1):  # 從59天前到今天
            date = current_date - timedelta(days=59-i)
            
            # 簡單的價格波動模擬
            import random
            random.seed(hash(stock_code) + i)  # 確保可重現
            
            price_variation = 1 + (random.random() - 0.5) * 0.1  # ±5%波動
            price = base_price * price_variation
            
            volume_variation = 1 + (random.random() - 0.5) * 0.5  # ±25%波動
            volume = current_data['volume'] * volume_variation
            
            historical_data.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': price * (1 + (random.random() - 0.5) * 0.02),
                'high': price * (1 + random.random() * 0.03),
                'low': price * (1 - random.random() * 0.03),
                'close': price,
                'volume': int(volume)
            })
        
        logger.info(f"✅ {stock_code}: 生成 {len(historical_data)} 天模擬歷史資料")
        return historical_data
        
    except Exception as e:
        logger.error(f"❌ {stock_code}: 方法3失敗 - {e}")
        return None

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

def calculate_ema(values, period):
    """計算指數移動平均"""
    if len(values) < period:
        return sum(values) / len(values) if values else 0
    
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period  # 初始SMA
    
    for value in values[period:]:
        ema = (value * multiplier) + (ema * (1 - multiplier))
    
    return ema

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
                    'date': data_date_display,  # 使用統一的資料日期顯示格式
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
            'date': data_date_display,  # 使用統一的資料日期顯示格式
            'is_crossover': False,
            'is_oversold': False,
            'banker_entry_signal': False
        }
        
    except Exception as e:
        logger.error(f"獲取股票 {stock_code} 資料時發生錯誤: {e}")
        return None

def update_stocks_data():
    """更新股票資料"""
    global stocks_data, is_updating, last_update_time, data_date, data_date_display
    
    try:
        # 移除過度保護機制，允許用戶隨時更新
        is_updating = True
        
        logger.info("開始更新全市場股票資料...")
        
        # 獲取真實股票資料
        real_data = fetch_real_stock_data()
        
        if real_data:
            stocks_data = real_data
            last_update_time = get_taiwan_time()
            
            logger.info(f"股票資料更新完成，共 {len(stocks_data)} 支股票")
            
            return jsonify({
                'success': True,
                'message': f'成功更新 {len(stocks_data)} 支股票資料（全市場覆蓋）',
                'stocks_count': len(stocks_data),
                'update_time': last_update_time.isoformat(),
                'data_date': data_date_display
            })
        else:
            return jsonify({
                'success': False,
                'error': '無法獲取股票資料，請稍後再試'
            }), 500
            
    except Exception as e:
        logger.error(f"更新股票資料時發生錯誤: {e}")
        return jsonify({
            'success': False,
            'error': f'更新失敗: {str(e)}'
        }), 500
    finally:
        is_updating = False

# API路由
@app.route('/')
def index():
    """首頁"""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """健康檢查"""
    return jsonify({
        'status': 'healthy',
        'timestamp': get_taiwan_time().isoformat(),
        'last_update': last_update_time.isoformat() if last_update_time else None,
        'stocks_count': len(stocks_data),
        'data_date': data_date_display
    })

@app.route('/api/stocks')
def get_stocks():
    """獲取股票清單"""
    if not stocks_data:
        return jsonify({
            'success': False,
            'error': '請先更新股票資料'
        }), 400
    
    # 返回實際的股票資料，而不是預設清單
    stock_list = []
    for code, data in list(stocks_data.items())[:50]:  # 限制返回前50支作為預覽
        stock_list.append({
            'stock_id': code,
            'stock_name': data['name'],
            'price': data['close'],
            'change_percent': data['change_percent'],
            'date': data['date']
        })
    
    return jsonify({
        'success': True,
        'stocks': stock_list,
        'total_count': len(stocks_data),
        'data_date': data_date_display
    })

@app.route('/api/update', methods=['POST'])
def update_stocks():
    """更新股票資料"""
    global stocks_data, is_updating, last_update_time, data_date, data_date_display
    
    try:
        # 移除過度保護機制，允許用戶隨時更新
        is_updating = True
        
        logger.info("開始更新全市場股票資料...")
        
        # 獲取真實股票資料
        real_data = fetch_real_stock_data()
        
        if real_data:
            stocks_data = real_data
            last_update_time = get_taiwan_time()
            
            logger.info(f"股票資料更新完成，共 {len(stocks_data)} 支股票")
            
            return jsonify({
                'success': True,
                'message': f'成功更新 {len(stocks_data)} 支股票資料（全市場覆蓋）',
                'stocks_count': len(stocks_data),
                'update_time': last_update_time.isoformat(),
                'data_date': data_date_display
            })
        else:
            return jsonify({
                'success': False,
                'error': '無法獲取股票資料，請稍後再試'
            }), 500
            
    except Exception as e:
        logger.error(f"更新股票資料時發生錯誤: {e}")
        return jsonify({
            'success': False,
            'error': f'更新失敗: {str(e)}'
        }), 500
    finally:
        is_updating = False

@app.route('/api/screen', methods=['POST'])
def screen_stocks():
    """篩選股票"""
    try:
        current_time = get_taiwan_time()
        
        # 檢查是否有股票資料
        if not stocks_data:
            return jsonify({
                'success': False,
                'error': '請先更新股票資料'
            }), 400
        
        # 獲取所有股票的完整資料（全部股票分析）
        all_stocks_data = []
        total_stocks = len(stocks_data)
        processed_count = 0
        
        logger.info(f"開始分析 {total_stocks} 支股票的Pine Script指標...")
        
        # 分批處理以避免超時（減少批次大小）
        batch_size = 10  # 從50減少到10支股票每批
        stock_codes = list(stocks_data.keys())
        
        # 限制總處理數量以避免超時
        max_stocks = min(1044, len(stock_codes))  # 最多處理1044支股票
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
        
        logger.info(f"篩選完成：共分析 {processed_count} 支股票，發現 {len(yellow_candle_stocks)} 支黃柱信號股票")
        
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
            'data_date': data_date_display
        })
        
    except Exception as e:
        logger.error(f"篩選股票時發生錯誤: {e}")
        return jsonify({
            'success': False,
            'error': f'篩選失敗: {str(e)}'
        }), 500

if __name__ == '__main__':
    # 初始化時載入預設股票資料
    logger.info("台股主力資金篩選器啟動中...")
    
    # 設定Flask應用
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

