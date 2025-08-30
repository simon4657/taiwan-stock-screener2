# 台股主力資金進入篩選器 - 上櫃市場版本

## 專案簡介

這是一個專門針對台灣上櫃市場的股票篩選器，使用Pine Script技術分析邏輯來識別主力資金進場信號。系統透過台灣櫃買中心的真實市場資料，提供準確的技術分析結果。

## 主要特色

### 🎯 專業技術分析
- **Pine Script邏輯**: 使用經過驗證的Pine Script技術指標
- **資金流向分析**: 計算Money Flow Index (MFI)指標
- **多空線指標**: 基於高低點的EMA計算
- **黃柱信號檢測**: 識別主力資金進場時機

### 📊 上櫃市場專用
- **資料來源**: 台灣櫃買中心OpenAPI
- **股票範圍**: 專門處理上櫃一般股票（1000-9999）
- **即時更新**: 支援最新交易日資料更新
- **市場標記**: 明確標示為上櫃市場(OTC)

### 🔧 系統功能
- **智能篩選**: 自動篩選符合條件的股票
- **投資評分**: 0-100分的投資參考評分
- **成交張數**: 台股本土化的成交量顯示
- **趨勢箭頭**: 直觀的技術指標趨勢顯示

## 技術架構

### 後端技術
- **Flask**: Python Web框架
- **Requests**: HTTP請求處理
- **PyTZ**: 台灣時區處理
- **Gunicorn**: 生產環境WSGI服務器

### 前端技術
- **原生JavaScript**: 無框架依賴
- **響應式設計**: 支援桌面和行動裝置
- **現代CSS**: 漸層背景和動畫效果

### 資料來源
- **台灣櫃買中心**: https://www.tpex.org.tw/openapi/
- **API端點**: `/v1/tpex_mainboard_daily_close_quotes`
- **更新頻率**: 每交易日更新

## 安裝與部署

### 本地開發

```bash
# 1. 安裝依賴
pip install -r requirements.txt

# 2. 啟動開發服務器
python app.py

# 3. 訪問應用
http://localhost:5000
```

### 生產部署

```bash
# 使用Gunicorn部署
gunicorn -c gunicorn.conf.py app:app
```

### Render部署

1. **連接GitHub倉庫**
2. **設定部署參數**:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn -c gunicorn.conf.py app:app`
3. **環境變數**: 無需額外設定

## API文檔

### 健康檢查
```
GET /api/health
```

回應範例:
```json
{
    "status": "healthy",
    "timestamp": "2025-08-24T12:13:50+08:00",
    "stocks_count": 839,
    "data_date": "1140822",
    "market": "OTC",
    "version": "4.0 - OTC Market Edition"
}
```

### 更新股票資料
```
POST /api/update
```

回應範例:
```json
{
    "success": true,
    "message": "成功更新 839 支上櫃股票資料",
    "stocks_count": 839,
    "data_date": "1140822",
    "market": "OTC"
}
```

### 股票篩選
```
POST /api/screen
Content-Type: application/json

{
    "stock_codes": ["1240", "1259"] // 可選，不提供則篩選所有股票
}
```

回應範例:
```json
{
    "success": true,
    "yellow_candle_stocks": [
        {
            "code": "1240",
            "name": "茂生農經",
            "close": 25.50,
            "change": "+0.15",
            "volume": 12000,
            "volume_lots": 12,
            "money_flow_index": 65.2,
            "bull_bear_line": 24.8,
            "investment_score": 75,
            "banker_entry_signal": true,
            "market": "OTC"
        }
    ],
    "total_analyzed": 800,
    "yellow_candle_count": 1,
    "market": "OTC"
}
```

## 技術指標說明

### 資金流向指標 (MFI)
- **計算方式**: 基於典型價格和成交量
- **數值範圍**: 0-100
- **信號意義**: >50表示資金流入，<50表示資金流出

### 多空線指標
- **計算方式**: 結合34期高低點基準線和13期EMA
- **信號意義**: 股價突破多空線表示趨勢轉強

### 黃柱信號條件
1. **資金流向**: MFI > 50 且 < 80
2. **價格突破**: 股價 > 多空線
3. **成交量**: 成交量放大20%以上

### 投資評分算法
- **MFI評分**: 30分 (根據MFI數值)
- **多空線評分**: 30分 (根據價格與多空線關係)
- **黃柱信號**: 25分 (符合條件加分)
- **成交量**: 15分 (根據成交量放大程度)

## 系統特色

### 資料準確性
- ✅ 使用台灣櫃買中心官方API
- ✅ 即時更新交易日資料
- ✅ 自動處理資料格式轉換
- ✅ 完整的錯誤處理機制

### 用戶體驗
- ✅ 響應式設計支援行動裝置
- ✅ 直觀的股票卡片顯示
- ✅ 即時狀態更新
- ✅ 載入動畫和進度提示

### 技術穩定性
- ✅ 經過驗證的Pine Script邏輯
- ✅ 完整的異常處理
- ✅ 生產環境部署配置
- ✅ 詳細的日誌記錄

## 版本資訊

- **版本**: 4.0 - OTC Market Edition
- **發布日期**: 2025年8月24日
- **適用市場**: 台灣上櫃市場
- **支援股票**: 839支上櫃一般股票

## 注意事項

### 投資風險提醒
- 本系統僅提供技術分析參考，不構成投資建議
- 投資有風險，請謹慎評估自身風險承受能力
- 過去績效不代表未來表現

### 技術限制
- 歷史資料使用模擬數據，實際應用建議使用真實歷史資料
- 系統處理能力限制為800支股票以避免超時
- 部分停牌或異常股票可能無法正常處理

## 支援與維護

如有技術問題或功能建議，請聯繫開發團隊。

---

**台股主力資金進入篩選器 - 上櫃市場版本**  
專業的上櫃股票技術分析工具，助您掌握主力資金動向！

