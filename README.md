# 台股主力資金進入篩選器 - Render部署版本

## 🎯 系統概述

這是一個基於真實台股資料的Pine Script主力進場篩選系統，使用台灣證券交易所官方API提供準確的技術分析結果。

## 🚀 Render部署指南

### 1. 準備工作
- 確保您有Render帳號 (https://render.com)
- 將此專案上傳到GitHub倉庫

### 2. 在Render創建Web Service
1. 登入Render控制台
2. 點擊「New +」→「Web Service」
3. 連接您的GitHub倉庫
4. 選擇此專案的倉庫

### 3. 部署設定
```
Name: taiwan-stock-screener
Environment: Python 3.12
Region: 選擇最近的區域
Branch: main (或您的主分支)

Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app

Instance Type: Free (或根據需求選擇)
```

### 4. 環境變數 (可選)
如需設定特殊環境變數，可在Render控制台的Environment頁面添加：
```
PORT: (Render會自動設定，無需手動添加)
```

### 5. 部署完成
- Render會自動開始建置和部署
- 部署成功後會提供一個 `.onrender.com` 的URL
- 首次啟動可能需要幾分鐘來初始化股票資料

## 📋 功能特色

### 真實資料來源
- **台灣證券交易所API**: 官方權威的股票交易資料
- **Yahoo Finance API**: 歷史資料支援技術指標計算
- **即時更新**: 支援手動更新最新市場資料

### Pine Script技術分析
- **資金流向趨勢**: 基於27期高低價計算
- **多空線**: 使用34期高低價和13期EMA
- **主力進場條件**: 
  - 資金流向突破多空線 (crossover)
  - 多空線處於超賣區 (< 25)

### 系統特性
- **響應式設計**: 支援桌面和行動裝置
- **CORS支援**: 允許跨域請求
- **錯誤處理**: 完善的異常處理機制
- **背景更新**: 非阻塞的資料更新

## 🔧 本地開發

### 安裝依賴
```bash
pip install -r requirements.txt
```

### 啟動應用
```bash
python app.py
```

### 訪問應用
```
http://localhost:10000
```

## 📊 使用方式

1. **更新股票資料**: 點擊「更新股票資料」按鈕獲取最新的台股資料
2. **開始篩選**: 點擊「開始篩選」按鈕執行Pine Script分析
3. **查看結果**: 系統會顯示符合主力進場條件的股票清單

## 🔍 技術架構

### 後端 (Flask)
- **API端點**: 
  - `GET /` - 主頁面
  - `GET /api/stocks` - 獲取股票清單
  - `POST /api/update` - 更新股票資料
  - `POST /api/screen` - 篩選股票
  - `GET /api/health` - 健康檢查

### 前端 (HTML/CSS/JavaScript)
- **響應式設計**: Bootstrap風格的現代化介面
- **即時更新**: JavaScript處理API呼叫和結果顯示
- **狀態管理**: 載入狀態和錯誤處理

### 資料處理
- **證交所API**: 獲取當日股票交易資料
- **Yahoo Finance API**: 獲取歷史資料用於技術指標計算
- **Pine Script邏輯**: 完整實現技術分析算法

## ⚠️ 注意事項

### 資料限制
- 證交所API提供前一交易日的資料
- 週末和假日無新資料更新
- 首次啟動需要時間初始化資料

### 效能考量
- 建議在交易日開盤前更新資料
- 避免頻繁更新造成API負載
- Render免費方案有使用時間限制

### 投資風險
- 本系統僅供技術分析參考
- 投資決策請自行承擔風險
- 建議結合其他分析工具使用

## 🆘 故障排除

### 常見問題
1. **部署失敗**: 檢查requirements.txt是否正確
2. **無法獲取資料**: 檢查網路連接和API狀態
3. **篩選無結果**: 這是正常現象，表示當前無股票符合嚴格條件

### 日誌檢查
在Render控制台的Logs頁面可以查看詳細的運行日誌。

## 📞 技術支援

如遇到技術問題，請檢查：
1. Render部署日誌
2. API連接狀態
3. 資料更新時間

---

**版本**: 真實資料版本 (Python 3.12)  
**更新日期**: 2025-07-27  
**適用平台**: Render.com

