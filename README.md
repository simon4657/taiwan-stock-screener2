# 台股主力資金進入篩選器 - Render部署修復版

## 專案簡介
這是一個專為Render平台優化的台股主力資金進入篩選器，具備強化的錯誤處理和降級模式運行能力。

## 主要特色
- ✅ **Render平台優化** - 專為Render免費方案設計
- ✅ **強化錯誤處理** - 即使組件初始化失敗也能正常運行
- ✅ **降級模式** - 在資料源不可用時使用模擬資料
- ✅ **移除undefined顯示** - 優化前端用戶體驗
- ✅ **無過度保護機制** - 用戶可隨時更新資料

## 部署說明

### Render部署設定
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python app.py`
- **Environment**: Python 3
- **Region**: Singapore (推薦)

### 環境變數
系統會自動適應Render的環境變數：
- `PORT` - 自動使用Render提供的端口
- `RENDER` - 檢測Render環境並啟用keep-alive機制

## 功能說明

### 核心功能
1. **股票資料更新** - 支援多重備用資料源
2. **主力資金篩選** - 智能分析主力進場信號
3. **即時排序** - 支援多種排序方式
4. **響應式設計** - 支援各種裝置

### API端點
- `GET /` - 主頁面
- `POST /api/stocks/update` - 更新股票資料
- `POST /api/stocks/screen` - 篩選股票
- `GET /api/task/status` - 獲取任務狀態
- `GET /health` - 健康檢查

## 技術架構
- **後端**: Flask + Python
- **前端**: HTML5 + CSS3 + JavaScript
- **資料處理**: Pandas + BeautifulSoup
- **部署平台**: Render

## 版本資訊
- **版本**: 1.0.1-fixed
- **更新日期**: 2024
- **修復項目**: Render部署問題、undefined顯示、過度保護機制

## 注意事項
- 本系統僅供參考，投資有風險
- 在Render免費方案下，30分鐘無活動會自動休眠
- 系統具備keep-alive機制，減少休眠頻率

