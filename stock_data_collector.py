import pandas as pd
import requests
from bs4 import BeautifulSoup
import logging

class StockDataCollector:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def get_taiwan_stock_list(self):
        """獲取台灣股票清單"""
        try:
            # 嘗試從網路獲取
            stock_list = self._get_stock_list_from_web()
            if not stock_list.empty:
                return stock_list
        except Exception as e:
            self.logger.warning(f"從網路獲取股票清單失敗: {e}")
        
        # 使用預設清單
        return self._get_default_stock_list()
    
    def _get_stock_list_from_web(self):
        """嘗試從網路獲取股票清單"""
        try:
            url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # 簡化的解析邏輯
                return pd.DataFrame()  # 返回空DataFrame，觸發使用預設清單
            
        except Exception as e:
            self.logger.error(f"網路獲取失敗: {e}")
        
        return pd.DataFrame()
    
    def _get_default_stock_list(self):
        """獲取預設股票清單"""
        default_stocks = [
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
        
        self.logger.info(f"使用預設股票清單，共 {len(default_stocks)} 支股票")
        return pd.DataFrame(default_stocks)
    
    def get_stock_data(self, stock_code):
        """獲取單支股票資料（簡化版）"""
        try:
            # 返回模擬資料
            return {
                'code': stock_code,
                'close_price': 100.0,
                'change_percent': 0.0,
                'volume': 1000
            }
        except Exception as e:
            self.logger.error(f"獲取股票 {stock_code} 資料失敗: {e}")
            return None

