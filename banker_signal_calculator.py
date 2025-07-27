import logging
import random

class BankerEntrySignalCalculator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def get_top_banker_entry_stocks(self, stocks_data, top_n=20):
        """獲取主力進場股票（簡化版）"""
        try:
            results = []
            
            # 生成模擬結果
            sample_stocks = [
                {'code': '2330', 'name': '台積電'},
                {'code': '2317', 'name': '鴻海'},
                {'code': '2454', 'name': '聯發科'},
                {'code': '2881', 'name': '富邦金'},
                {'code': '2882', 'name': '國泰金'}
            ]
            
            for stock in sample_stocks:
                result = {
                    'code': stock['code'],
                    'name': stock['name'],
                    'close_price': round(random.uniform(50, 1000), 2),
                    'change_percent': round(random.uniform(-3, 5), 2),
                    'fund_trend': random.choice(['流入', '流出', '持平']),
                    'multi_short_line': random.choice(['多頭', '空頭', '盤整']),
                    'entry_score': random.randint(60, 95)
                }
                results.append(result)
            
            # 按評分排序
            results.sort(key=lambda x: x['entry_score'], reverse=True)
            
            self.logger.info(f"生成 {len(results)} 支股票的模擬分析結果")
            return results[:top_n]
            
        except Exception as e:
            self.logger.error(f"計算主力進場信號失敗: {e}")
            return []
    
    def calculate_banker_signal(self, stock_data):
        """計算單支股票的主力信號（簡化版）"""
        try:
            # 返回模擬信號
            return {
                'entry_score': random.randint(60, 95),
                'fund_trend': random.choice(['流入', '流出', '持平']),
                'multi_short_line': random.choice(['多頭', '空頭', '盤整'])
            }
        except Exception as e:
            self.logger.error(f"計算主力信號失敗: {e}")
            return None

