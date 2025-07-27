from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import logging
import threading
import time
import os
from datetime import datetime, timedelta
import requests
import json
import urllib3

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
data_date = None  # 資料日期

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
    """獲取最近的交易日期（排除週末）"""
    today = datetime.now()
    
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
        
        # 處理資料格式（處理所有股票）
        processed_data = {}
        valid_stocks = 0
        
        for item in data:
            stock_code = item.get('Code', '').strip()
            stock_name = item.get('Name', '').strip()
            
            # 過濾條件：只處理有效的股票代碼
            if (stock_code and 
                len(stock_code) == 4 and 
                stock_code.isdigit() and
                stock_name and
                not any(keyword in stock_name for keyword in ['DR', 'TDR', 'ETF', 'ETN', '權證', '特別股'])):
                
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
                            'date': item.get('Date', get_latest_trading_date())
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
    """獲取歷史資料用於技術指標計算（使用Yahoo Finance API）"""
    try:
        # 使用Manus API Hub的Yahoo Finance API
        import sys
        sys.path.append('/opt/.manus/.sandbox-runtime')
        from data_api import ApiClient
        
        client = ApiClient()
        
        # 台股代碼需要加上.TW後綴
        symbol = f"{stock_code}.TW"
        
        response = client.call_api('YahooFinance/get_stock_chart', query={
            'symbol': symbol,
            'region': 'TW',
            'interval': '1d',
            'range': '3mo',  # 3個月歷史資料
            'includeAdjustedClose': True
        })
        
        if not response or 'chart' not in response or 'result' not in response['chart']:
            return None
        
        result = response['chart']['result'][0]
        timestamps = result['timestamp']
        quotes = result['indicators']['quote'][0]
        
        # 轉換為OHLC格式
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
        
        return ohlc_data[-days:] if len(ohlc_data) > days else ohlc_data
        
    except Exception as e:
        # 靜默處理錯誤，避免日誌過多
        return None

def calculate_weighted_simple_average(values, length, weight):
    """計算加權簡單平均（模擬Pine Script函數）"""
    if len(values) < length:
        return values[-1] if values else 0
    
    # 簡化的加權移動平均計算
    recent_values = values[-length:]
    weighted_sum = sum(val * (i + 1) for i, val in enumerate(recent_values))
    weight_sum = sum(range(1, length + 1))
    return weighted_sum / weight_sum if weight_sum > 0 else 0

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
        return None, None, False
    
    # 提取OHLC數據
    closes = [d['close'] for d in ohlc_data]
    highs = [d['high'] for d in ohlc_data]
    lows = [d['low'] for d in ohlc_data]
    opens = [d['open'] for d in ohlc_data]
    
    # 計算典型價格 (2 * close + high + low + open) / 5
    typical_prices = [(2 * c + h + l + o) / 5 for c, h, l, o in zip(closes, highs, lows, opens)]
    
    # 計算27期最高最低價
    lowest_27 = [min(lows[max(0, i-26):i+1]) for i in range(len(lows))]
    highest_27 = [max(highs[max(0, i-26):i+1]) for i in range(len(highs))]
    
    # 計算34期最高最低價
    lowest_34 = [min(lows[max(0, i-33):i+1]) for i in range(len(lows))]
    highest_34 = [max(highs[max(0, i-33):i+1]) for i in range(len(highs))]
    
    # 計算資金流向趨勢（簡化版Pine Script公式）
    fund_flow_values = []
    for i in range(len(closes)):
        if highest_27[i] != lowest_27[i]:
            relative_position = (closes[i] - lowest_27[i]) / (highest_27[i] - lowest_27[i]) * 100
        else:
            relative_position = 50
        
        # 簡化的加權平均計算
        if i >= 5:
            wsa1 = calculate_weighted_simple_average([relative_position], 5, 1)
            wsa2 = calculate_weighted_simple_average([wsa1], 3, 1)
            fund_flow = (3 * wsa1 - 2 * wsa2 - 50) * 1.032 + 50
        else:
            fund_flow = relative_position
        
        fund_flow_values.append(max(0, min(100, fund_flow)))  # 限制在0-100範圍
    
    # 計算多空線（13期EMA）
    bull_bear_values = []
    for i in range(len(typical_prices)):
        if highest_34[i] != lowest_34[i]:
            normalized_price = (typical_prices[i] - lowest_34[i]) / (highest_34[i] - lowest_34[i]) * 100
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
    
    # 檢查crossover條件
    if len(fund_flow_values) >= 2 and len(bull_bear_line_values) >= 2:
        current_fund = fund_flow_values[-1]
        previous_fund = fund_flow_values[-2]
        current_bull_bear = bull_bear_line_values[-1]
        previous_bull_bear = bull_bear_line_values[-2]
        
        # Pine Script crossover邏輯：ta.crossover(fund_flow_trend, bull_bear_line)
        is_crossover = (current_fund > current_bull_bear) and (previous_fund <= previous_bull_bear)
        is_oversold = current_bull_bear < 25
        
        banker_entry_signal = is_crossover and is_oversold
        
        # 記錄詳細計算結果用於調試（僅記錄符合條件的股票）
        if banker_entry_signal:
            logger.info(f"發現符合條件股票 - {stock_code if 'stock_code' in locals() else 'Unknown'}:")
            logger.info(f"  資金流向趨勢: {current_fund:.2f} (前期: {previous_fund:.2f})")
            logger.info(f"  多空線: {current_bull_bear:.2f} (前期: {previous_bull_bear:.2f})")
            logger.info(f"  crossover: {is_crossover}")
            logger.info(f"  超賣區: {is_oversold}")
            logger.info(f"  主力進場信號: {banker_entry_signal}")
        
        return current_fund, current_bull_bear, banker_entry_signal, is_crossover, is_oversold
    
    return None, None, False, False, False

def get_stock_web_data(stock_code, stock_name=None):
    """獲取股票的完整資料（結合即時資料和技術指標）"""
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
                'date': current_data['date'],
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
            fund_flow_trend, bull_bear_line, banker_entry_signal, is_crossover, is_oversold = result
            
            if fund_flow_trend is not None:
                # 根據嚴格的Pine Script條件判斷狀態
                if banker_entry_signal:
                    signal_status = "主力進場"
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
                
                return {
                    'name': stock_name or current_data['name'],
                    'price': current_data['close'],
                    'change_percent': current_data['change_percent'],
                    'fund_trend': f"{fund_flow_trend:.2f}",
                    'multi_short_line': f"{bull_bear_line:.2f}",
                    'signal_status': signal_status,
                    'score': score,
                    'date': current_data['date'],
                    'is_crossover': is_crossover,
                    'is_oversold': is_oversold,
                    'banker_entry_signal': banker_entry_signal
                }
        
        # 如果無法計算技術指標，返回基本資料
        logger.warning(f"股票 {stock_code} 歷史資料不足，無法計算技術指標")
        return {
            'name': stock_name or current_data['name'],
            'price': current_data['close'],
            'change_percent': current_data['change_percent'],
            'fund_trend': "資料不足",
            'multi_short_line': "資料不足",
            'signal_status': "資料不足",
            'score': 0,
            'date': current_data['date']
        }
        
    except Exception as e:
        logger.error(f"獲取股票 {stock_code} 資料時發生錯誤: {e}")
        return None

def update_stocks_data():
    """更新股票資料"""
    global stocks_data, is_updating, last_update_time, data_date
    
    if is_updating:
        logger.info("股票資料更新已在進行中，跳過此次更新")
        return
    
    is_updating = True
    logger.info("開始更新股票資料...")
    
    try:
        # 獲取真實股票資料
        real_data = fetch_real_stock_data()
        
        if real_data:
            stocks_data = real_data
            last_update_time = datetime.now()
            
            # 設定資料日期（使用第一支股票的日期）
            if stocks_data:
                first_stock = next(iter(stocks_data.values()))
                data_date = first_stock.get('date', get_latest_trading_date())
            
            logger.info(f"股票資料更新完成，共更新 {len(stocks_data)} 支股票")
        else:
            logger.error("無法獲取真實股票資料")
            
    except Exception as e:
        logger.error(f"更新股票資料時發生錯誤: {e}")
    finally:
        is_updating = False

@app.route('/')
def index():
    """首頁"""
    return render_template('index.html')

@app.route('/api/stocks')
def get_stocks():
    """獲取股票清單"""
    try:
        stock_list = get_default_stock_list()
        return jsonify({
            'success': True,
            'data': stock_list,
            'last_update': last_update_time.isoformat() if last_update_time else None,
            'data_date': data_date
        })
    except Exception as e:
        logger.error(f"獲取股票清單時發生錯誤: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update', methods=['POST'])
def update_stocks():
    """更新股票資料"""
    global stocks_data, is_updating, last_update_time, data_date
    
    try:
        # 移除過度保護機制，允許用戶隨時更新
        is_updating = True
        
        logger.info("開始更新全市場股票資料...")
        
        # 獲取真實股票資料
        real_data = fetch_real_stock_data()
        
        if real_data:
            stocks_data = real_data
            last_update_time = datetime.now()
            data_date = get_latest_trading_date()
            
            logger.info(f"股票資料更新完成，共 {len(stocks_data)} 支股票")
            
            return jsonify({
                'success': True,
                'message': f'成功更新 {len(stocks_data)} 支股票資料（全市場覆蓋）',
                'stocks_count': len(stocks_data),
                'update_time': last_update_time.isoformat(),
                'data_date': data_date
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
        current_time = datetime.now()
        
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
        
        # 分批處理以避免超時
        batch_size = 50  # 每批處理50支股票
        stock_codes = list(stocks_data.keys())
        
        for i in range(0, len(stock_codes), batch_size):
            batch_codes = stock_codes[i:i+batch_size]
            logger.info(f"處理第 {i//batch_size + 1} 批股票 ({len(batch_codes)} 支)...")
            
            for stock_code in batch_codes:
                try:
                    stock_name = stocks_data[stock_code]['name']
                    stock_data = get_stock_web_data(stock_code, stock_name)
                    
                    if stock_data:
                        all_stocks_data.append({
                            'code': stock_code,
                            **stock_data
                        })
                        processed_count += 1
                        
                        # 每處理10支股票記錄一次進度
                        if processed_count % 10 == 0:
                            logger.info(f"已處理 {processed_count}/{total_stocks} 支股票...")
                            
                except Exception as e:
                    logger.warning(f"處理股票 {stock_code} 時發生錯誤: {e}")
                    continue
        
        logger.info(f"完成股票分析，共處理 {processed_count} 支股票")
        
        # 篩選符合Pine Script主力進場條件的股票（嚴格條件）
        filtered_stocks = []
        analysis_details = []
        
        for stock in all_stocks_data:
            # 記錄分析詳情
            analysis_details.append({
                'code': stock['code'],
                'name': stock['name'],
                'fund_trend': stock['fund_trend'],
                'multi_short_line': stock['multi_short_line'],
                'is_crossover': stock.get('is_crossover', False),
                'is_oversold': stock.get('is_oversold', False),
                'banker_entry_signal': stock.get('banker_entry_signal', False),
                'signal_status': stock['signal_status']
            })
            
            # 嚴格的Pine Script主力進場條件：只有banker_entry_signal為True才符合
            if stock.get('banker_entry_signal', False):
                filtered_stocks.append(stock)
        
        # 按評分排序
        filtered_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        # 記錄篩選結果
        logger.info(f"Pine Script篩選結果:")
        logger.info(f"  總共分析: {len(all_stocks_data)} 支股票")
        logger.info(f"  符合條件: {len(filtered_stocks)} 支股票")
        
        for detail in analysis_details:
            logger.info(f"  {detail['code']} {detail['name']}: 資金流向={detail['fund_trend']}, 多空線={detail['multi_short_line']}, crossover={detail['is_crossover']}, 超賣={detail['is_oversold']}, 主力進場={detail['banker_entry_signal']}")
        
        return jsonify({
            'success': True,
            'data': filtered_stocks,
            'total': len(filtered_stocks),
            'message': f'全市場Pine Script篩選：{len(filtered_stocks)} 支符合主力進場條件（分析 {processed_count} 支股票）',
            'query_time': current_time.isoformat(),
            'data_date': data_date,
            'analysis_summary': {
                'total_analyzed': processed_count,
                'total_available': total_stocks,
                'meets_criteria': len(filtered_stocks),
                'criteria': 'crossover(資金流向, 多空線) AND 多空線 < 25',
                'market_coverage': f'{(processed_count/total_stocks*100):.1f}%' if total_stocks > 0 else '0%'
            }
        })
        
    except Exception as e:
        logger.error(f"篩選股票時發生錯誤: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    """健康檢查"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'stocks_count': len(stocks_data),
        'last_update': last_update_time.isoformat() if last_update_time else None,
        'data_date': data_date,
        'is_updating': is_updating
    })

if __name__ == '__main__':
    # 啟動時更新一次股票資料
    logger.info("應用啟動，開始初始化股票資料...")
    update_stocks_data()
    
    # 啟動Flask應用 - 適配Render環境
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

