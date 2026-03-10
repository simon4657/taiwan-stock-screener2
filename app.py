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

# 非同步更新狀態
import threading
update_status = {
    'is_running': False,
    'progress': 0,
    'total': 0,
    'message': '',
    'success': None,  # None=未開始, True=成功, False=失敗
    'started_at': None,
    'finished_at': None
}
update_lock = threading.Lock()

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

# ====== 內建上市股票清單（2026-03-06 更新）======
# 此清單用於 Render 等海外環境（TWSE API 被封鎖時的備用方案）
BUILTIN_TWSE_STOCK_LIST = {
    "1101": "台泥",
    "1102": "亞泥",
    "1103": "嘉泥",
    "1104": "環泥",
    "1108": "幸福",
    "1109": "信大",
    "1110": "東泥",
    "1201": "味全",
    "1203": "味王",
    "1210": "大成",
    "1213": "大飲",
    "1215": "卜蜂",
    "1216": "統一",
    "1217": "愛之味",
    "1218": "泰山",
    "1219": "福壽",
    "1220": "台榮",
    "1225": "福懋油",
    "1227": "佳格",
    "1229": "聯華",
    "1231": "聯華食",
    "1232": "大統益",
    "1233": "天仁",
    "1234": "黑松",
    "1235": "興泰",
    "1236": "宏亞",
    "1256": "鮮活果汁-KY",
    "1301": "台塑",
    "1303": "南亞",
    "1304": "台聚",
    "1305": "華夏",
    "1307": "三芳",
    "1308": "亞聚",
    "1309": "台達化",
    "1310": "台苯",
    "1312": "國喬",
    "1313": "聯成",
    "1314": "中石化",
    "1315": "達新",
    "1316": "上曜",
    "1319": "東陽",
    "1321": "大洋",
    "1323": "永裕",
    "1324": "地球",
    "1325": "恆大",
    "1326": "台化",
    "1337": "再生-KY",
    "1338": "廣華-KY",
    "1339": "昭輝",
    "1340": "勝悅-KY",
    "1341": "富林-KY",
    "1342": "八貫",
    "1402": "遠東新",
    "1409": "新纖",
    "1410": "南染",
    "1413": "宏洲",
    "1414": "東和",
    "1416": "廣豐",
    "1417": "嘉裕",
    "1418": "東華",
    "1419": "新紡",
    "1423": "利華",
    "1432": "大魯閣",
    "1434": "福懋",
    "1435": "中福",
    "1436": "華友聯",
    "1437": "勤益控",
    "1438": "三地開發",
    "1439": "雋揚",
    "1440": "南紡",
    "1441": "大東",
    "1442": "名軒",
    "1443": "立益物流",
    "1444": "力麗",
    "1445": "大宇",
    "1446": "宏和",
    "1447": "力鵬",
    "1449": "佳和",
    "1451": "年興",
    "1452": "宏益",
    "1453": "大將",
    "1454": "台富",
    "1455": "集盛",
    "1456": "怡華",
    "1457": "宜進",
    "1459": "聯發",
    "1460": "宏遠",
    "1463": "強盛新",
    "1464": "得力",
    "1465": "偉全",
    "1466": "聚隆",
    "1467": "南緯",
    "1468": "昶和",
    "1470": "大統新創",
    "1471": "首利",
    "1472": "三洋實業",
    "1473": "台南",
    "1474": "弘裕",
    "1475": "業旺",
    "1476": "儒鴻",
    "1477": "聚陽",
    "1503": "士電",
    "1504": "東元",
    "1506": "正道",
    "1512": "瑞利",
    "1513": "中興電",
    "1514": "亞力",
    "1515": "力山",
    "1516": "川飛",
    "1517": "利奇",
    "1519": "華城",
    "1521": "大億",
    "1522": "堤維西",
    "1524": "耿鼎",
    "1525": "江申",
    "1526": "日馳",
    "1527": "鑽全",
    "1528": "恩德",
    "1529": "樂事綠能",
    "1530": "亞崴",
    "1531": "高林股",
    "1532": "勤美",
    "1533": "車王電",
    "1535": "中宇",
    "1536": "和大",
    "1537": "廣隆",
    "1538": "正峰",
    "1539": "巨庭",
    "1540": "喬福",
    "1541": "錩泰",
    "1558": "伸興",
    "1560": "中砂",
    "1563": "巧新",
    "1568": "倉佑",
    "1582": "信錦",
    "1583": "程泰",
    "1587": "吉茂",
    "1589": "永冠-KY",
    "1590": "亞德客-KY",
    "1597": "直得",
    "1598": "岱宇",
    "1603": "華電",
    "1604": "聲寶",
    "1605": "華新",
    "1608": "華榮",
    "1609": "大亞",
    "1611": "中電",
    "1612": "宏泰",
    "1614": "三洋電",
    "1615": "大山",
    "1616": "億泰",
    "1617": "榮星",
    "1618": "合機",
    "1623": "大東電",
    "1626": "艾美特-KY",
    "1702": "南僑",
    "1707": "葡萄王",
    "1708": "東鹼",
    "1709": "和益",
    "1710": "東聯",
    "1711": "永光",
    "1712": "興農",
    "1713": "國化",
    "1714": "和桐",
    "1717": "長興",
    "1718": "中纖",
    "1720": "生達",
    "1721": "三晃",
    "1722": "台肥",
    "1723": "中碳",
    "1725": "元禎",
    "1726": "永記",
    "1727": "中華化",
    "1730": "花仙子",
    "1731": "美吾華",
    "1732": "毛寶",
    "1733": "五鼎",
    "1734": "杏輝",
    "1735": "日勝化",
    "1736": "喬山",
    "1737": "臺鹽",
    "1752": "南光",
    "1760": "寶齡富錦",
    "1762": "中化生",
    "1773": "勝一",
    "1776": "展宇",
    "1783": "和康生",
    "1786": "科妍",
    "1789": "神隆",
    "1795": "美時",
    "1802": "台玻",
    "1805": "寶徠",
    "1806": "冠軍",
    "1808": "潤隆",
    "1809": "中釉",
    "1810": "和成",
    "1817": "凱撒衛",
    "1903": "士紙",
    "1904": "正隆",
    "1905": "華紙",
    "1906": "寶隆",
    "1907": "永豐餘",
    "1909": "榮成",
    "2002": "中鋼",
    "2006": "東和鋼鐵",
    "2007": "燁興",
    "2008": "高興昌",
    "2009": "第一銅",
    "2010": "春源",
    "2012": "春雨",
    "2013": "中鋼構",
    "2014": "中鴻",
    "2015": "豐興",
    "2017": "官田鋼",
    "2020": "美亞",
    "2022": "聚亨",
    "2023": "燁輝",
    "2024": "志聯",
    "2025": "千興",
    "2027": "大成鋼",
    "2028": "威致",
    "2029": "盛餘",
    "2030": "彰源",
    "2031": "新光鋼",
    "2032": "新鋼",
    "2033": "佳大",
    "2034": "允強",
    "2038": "海光",
    "2049": "上銀",
    "2059": "川湖",
    "2062": "橋椿",
    "2069": "運錩",
    "2101": "南港",
    "2102": "泰豐",
    "2103": "台橡",
    "2104": "國際中橡",
    "2105": "正新",
    "2106": "建大",
    "2107": "厚生",
    "2108": "南帝",
    "2109": "華豐",
    "2114": "鑫永銓",
    "2115": "六暉-KY",
    "2201": "裕隆",
    "2204": "中華",
    "2206": "三陽工業",
    "2207": "和泰車",
    "2208": "台船",
    "2211": "長榮鋼",
    "2227": "裕日車",
    "2228": "劍麟",
    "2231": "為升",
    "2233": "宇隆",
    "2236": "百達-KY",
    "2239": "英利-KY",
    "2241": "艾姆勒",
    "2243": "宏旭-KY",
    "2247": "汎德永業",
    "2248": "華勝-KY",
    "2250": "IKKA-KY",
    "2254": "巨鎧精密-創",
    "2258": "鴻華先進-創",
    "2301": "光寶科",
    "2302": "麗正",
    "2303": "聯電",
    "2305": "全友",
    "2308": "台達電",
    "2312": "金寶",
    "2313": "華通",
    "2314": "台揚",
    "2316": "楠梓電",
    "2317": "鴻海",
    "2321": "東訊",
    "2323": "中環",
    "2324": "仁寶",
    "2327": "國巨*",
    "2328": "廣宇",
    "2329": "華泰",
    "2330": "台積電",
    "2331": "精英",
    "2332": "友訊",
    "2337": "旺宏",
    "2338": "光罩",
    "2340": "台亞",
    "2342": "茂矽",
    "2344": "華邦電",
    "2345": "智邦",
    "2347": "聯強",
    "2348": "海悅",
    "2349": "錸德",
    "2351": "順德",
    "2352": "佳世達",
    "2353": "宏碁",
    "2354": "鴻準",
    "2355": "敬鵬",
    "2356": "英業達",
    "2357": "華碩",
    "2359": "所羅門",
    "2360": "致茂",
    "2362": "藍天",
    "2363": "矽統",
    "2364": "倫飛",
    "2365": "昆盈",
    "2367": "燿華",
    "2368": "金像電",
    "2369": "菱生",
    "2371": "大同",
    "2373": "震旦行",
    "2374": "佳能",
    "2375": "凱美",
    "2376": "技嘉",
    "2377": "微星",
    "2379": "瑞昱",
    "2380": "虹光",
    "2382": "廣達",
    "2383": "台光電",
    "2385": "群光",
    "2387": "精元",
    "2388": "威盛",
    "2390": "云辰",
    "2392": "正崴",
    "2393": "億光",
    "2395": "研華",
    "2397": "友通",
    "2399": "映泰",
    "2401": "凌陽",
    "2402": "毅嘉",
    "2404": "漢唐",
    "2405": "輔信",
    "2406": "國碩",
    "2408": "南亞科",
    "2409": "友達",
    "2412": "中華電",
    "2413": "環科",
    "2414": "精技",
    "2415": "錩新",
    "2417": "圓剛",
    "2419": "仲琦",
    "2420": "新巨",
    "2421": "建準",
    "2423": "固緯",
    "2424": "隴華",
    "2425": "承啟",
    "2426": "鼎元",
    "2427": "三商電",
    "2428": "興勤",
    "2429": "銘旺科",
    "2430": "燦坤",
    "2431": "聯昌",
    "2432": "倚天酷碁-創",
    "2433": "互盛電",
    "2434": "統懋",
    "2436": "偉詮電",
    "2438": "翔耀",
    "2439": "美律",
    "2440": "太空梭",
    "2441": "超豐",
    "2442": "新美齊",
    "2444": "兆勁",
    "2449": "京元電子",
    "2450": "神腦",
    "2451": "創見",
    "2453": "凌群",
    "2454": "聯發科",
    "2455": "全新",
    "2457": "飛宏",
    "2458": "義隆",
    "2459": "敦吉",
    "2460": "建通",
    "2461": "光群雷",
    "2462": "良得電",
    "2464": "盟立",
    "2465": "麗臺",
    "2466": "冠西電",
    "2467": "志聖",
    "2468": "華經",
    "2471": "資通",
    "2472": "立隆電",
    "2474": "可成",
    "2476": "鉅祥",
    "2477": "美隆電",
    "2478": "大毅",
    "2480": "敦陽科",
    "2481": "強茂",
    "2482": "連宇",
    "2483": "百容",
    "2484": "希華",
    "2485": "兆赫",
    "2486": "一詮",
    "2488": "漢平",
    "2489": "瑞軒",
    "2491": "吉祥全",
    "2492": "華新科",
    "2493": "揚博",
    "2495": "普安",
    "2496": "卓越",
    "2497": "怡利電",
    "2498": "宏達電",
    "2501": "國建",
    "2504": "國產",
    "2505": "國揚",
    "2506": "太設",
    "2509": "全坤建",
    "2511": "太子",
    "2514": "龍邦",
    "2515": "中工",
    "2516": "新建",
    "2520": "冠德",
    "2524": "京城",
    "2527": "宏璟",
    "2528": "皇普",
    "2530": "華建",
    "2534": "宏盛",
    "2535": "達欣工",
    "2536": "宏普",
    "2537": "聯上發",
    "2538": "基泰",
    "2539": "櫻花建",
    "2540": "愛山林",
    "2542": "興富發",
    "2543": "皇昌",
    "2545": "皇翔",
    "2546": "根基",
    "2547": "日勝生",
    "2548": "華固",
    "2597": "潤弘",
    "2601": "益航",
    "2603": "長榮",
    "2605": "新興",
    "2606": "裕民",
    "2607": "榮運",
    "2608": "嘉里大榮",
    "2609": "陽明",
    "2610": "華航",
    "2611": "志信",
    "2612": "中航",
    "2613": "中櫃",
    "2614": "東森",
    "2615": "萬海",
    "2616": "山隆",
    "2617": "台航",
    "2618": "長榮航",
    "2630": "亞航",
    "2633": "台灣高鐵",
    "2634": "漢翔",
    "2636": "台驊控股",
    "2637": "慧洋-KY",
    "2642": "宅配通",
    "2645": "長榮航太",
    "2646": "星宇航空",
    "2701": "萬企",
    "2702": "華園",
    "2704": "國賓",
    "2705": "六福",
    "2706": "第一店",
    "2707": "晶華",
    "2712": "遠雄來",
    "2722": "夏都",
    "2723": "美食-KY",
    "2727": "王品",
    "2731": "雄獅",
    "2739": "寒舍",
    "2748": "雲品",
    "2753": "八方雲集",
    "2762": "世界健身-KY",
    "2801": "彰銀",
    "2812": "台中銀",
    "2816": "旺旺保",
    "2820": "華票",
    "2832": "台產",
    "2834": "臺企銀",
    "2836": "高雄銀",
    "2838": "聯邦銀",
    "2845": "遠東銀",
    "2849": "安泰銀",
    "2850": "新產",
    "2851": "中再保",
    "2852": "第一保",
    "2855": "統一證",
    "2867": "三商壽",
    "2880": "華南金",
    "2881": "富邦金",
    "2882": "國泰金",
    "2883": "凱基金",
    "2884": "玉山金",
    "2885": "元大金",
    "2886": "兆豐金",
    "2887": "台新新光金",
    "2889": "國票金",
    "2890": "永豐金",
    "2891": "中信金",
    "2892": "第一金",
    "2897": "王道銀行",
    "2901": "欣欣",
    "2903": "遠百",
    "2904": "匯僑",
    "2905": "三商",
    "2906": "高林",
    "2908": "特力",
    "2910": "統領",
    "2911": "麗嬰房",
    "2912": "統一超",
    "2913": "農林",
    "2915": "潤泰全",
    "2923": "鼎固-KY",
    "2929": "淘帝-KY",
    "2939": "永邑-KY",
    "2945": "三商家購",
    "3002": "歐格",
    "3003": "健和興",
    "3004": "豐達科",
    "3005": "神基",
    "3006": "晶豪科",
    "3008": "大立光",
    "3010": "華立",
    "3011": "今皓",
    "3013": "晟銘電",
    "3014": "聯陽",
    "3015": "全漢",
    "3016": "嘉晶",
    "3017": "奇鋐",
    "3018": "隆銘綠能",
    "3019": "亞光",
    "3021": "鴻名",
    "3022": "威強電",
    "3023": "信邦",
    "3024": "憶聲",
    "3025": "星通",
    "3026": "禾伸堂",
    "3027": "盛達",
    "3028": "增你強",
    "3029": "零壹",
    "3030": "德律",
    "3031": "佰鴻",
    "3032": "偉訓",
    "3033": "威健",
    "3034": "聯詠",
    "3035": "智原",
    "3036": "文曄",
    "3037": "欣興",
    "3038": "全台",
    "3040": "遠見",
    "3041": "揚智",
    "3042": "晶技",
    "3043": "科風",
    "3044": "健鼎",
    "3045": "台灣大",
    "3046": "建碁",
    "3047": "訊舟",
    "3048": "益登",
    "3049": "精金",
    "3050": "鈺德",
    "3051": "力特",
    "3052": "夆典",
    "3054": "立萬利",
    "3055": "蔚華科",
    "3056": "富華新",
    "3057": "喬鼎",
    "3058": "立德",
    "3059": "華晶科",
    "3060": "銘異",
    "3062": "建漢",
    "3090": "日電貿",
    "3092": "鴻碩",
    "3094": "聯傑",
    "3130": "一零四",
    "3135": "凌航",
    "3138": "耀登",
    "3149": "正達",
    "3150": "鈺寶-創",
    "3164": "景岳",
    "3167": "大量",
    "3168": "眾福科",
    "3189": "景碩",
    "3209": "全科",
    "3229": "晟鈦",
    "3231": "緯創",
    "3257": "虹冠電",
    "3266": "昇陽",
    "3296": "勝德",
    "3305": "昇貿",
    "3308": "聯德",
    "3311": "閎暉",
    "3312": "弘憶股",
    "3321": "同泰",
    "3338": "泰碩",
    "3346": "麗清",
    "3356": "奇偶",
    "3376": "新日興",
    "3380": "明泰",
    "3406": "玉晶光",
    "3413": "京鼎",
    "3416": "融程電",
    "3419": "譁裕",
    "3432": "台端",
    "3437": "榮創",
    "3443": "創意",
    "3447": "展達",
    "3450": "聯鈞",
    "3454": "晶睿",
    "3481": "群創",
    "3494": "誠研",
    "3501": "維熹",
    "3504": "揚明光",
    "3515": "華擎",
    "3518": "柏騰",
    "3528": "安馳",
    "3530": "晶相光",
    "3532": "台勝科",
    "3533": "嘉澤",
    "3535": "晶彩科",
    "3543": "州巧",
    "3545": "敦泰",
    "3550": "聯穎",
    "3557": "嘉威",
    "3563": "牧德",
    "3576": "聯合再生",
    "3583": "辛耘",
    "3588": "通嘉",
    "3591": "艾笛森",
    "3592": "瑞鼎",
    "3593": "力銘",
    "3596": "智易",
    "3605": "宏致",
    "3607": "谷崧",
    "3617": "碩天",
    "3622": "洋華",
    "3645": "達邁",
    "3652": "精聯",
    "3653": "健策",
    "3661": "世芯-KY",
    "3665": "貿聯-KY",
    "3669": "圓展",
    "3673": "TPK-KY",
    "3679": "新至陞",
    "3686": "達能",
    "3694": "海華",
    "3701": "大眾控",
    "3702": "大聯大",
    "3703": "欣陸",
    "3704": "合勤控",
    "3705": "永信",
    "3706": "神達",
    "3708": "上緯投控",
    "3711": "日月光投控",
    "3712": "永崴投控",
    "3714": "富采",
    "3715": "定穎投控",
    "3716": "中化控股",
    "3717": "聯嘉投控",
    "4104": "佳醫",
    "4106": "雃博",
    "4108": "懷特",
    "4119": "旭富",
    "4133": "亞諾法",
    "4137": "麗豐-KY",
    "4142": "國光生",
    "4148": "全宇生技-KY",
    "4155": "訊映",
    "4164": "承業醫",
    "4190": "佐登-KY",
    "4306": "炎洲",
    "4414": "如興",
    "4426": "利勤",
    "4438": "廣越",
    "4439": "冠星-KY",
    "4440": "宜新實業",
    "4441": "振大環球",
    "4526": "東台",
    "4532": "瑞智",
    "4536": "拓凱",
    "4540": "全球傳動",
    "4545": "銘鈺",
    "4551": "智伸科",
    "4552": "力達-KY",
    "4555": "氣立",
    "4557": "永新-KY",
    "4560": "強信-KY",
    "4562": "穎漢",
    "4564": "元翎",
    "4566": "時碩工業",
    "4569": "六方科-KY",
    "4571": "鈞興-KY",
    "4572": "駐龍",
    "4576": "大銀微系統",
    "4581": "光隆精密-KY",
    "4583": "台灣精銳",
    "4585": "達明",
    "4588": "玖鼎電力",
    "4590": "富田-創",
    "4720": "德淵",
    "4722": "國精化",
    "4736": "泰博",
    "4737": "華廣",
    "4739": "康普",
    "4746": "台耀",
    "4755": "三福化",
    "4763": "材料*-KY",
    "4764": "雙鍵",
    "4766": "南寶",
    "4770": "上品",
    "4771": "望隼",
    "4807": "日成-KY",
    "4904": "遠傳",
    "4906": "正文",
    "4912": "聯德控股-KY",
    "4915": "致伸",
    "4916": "事欣科",
    "4919": "新唐",
    "4927": "泰鼎-KY",
    "4930": "燦星網",
    "4934": "太極",
    "4935": "茂林-KY",
    "4938": "和碩",
    "4942": "嘉彰",
    "4943": "康控-KY",
    "4949": "有成精密",
    "4952": "凌通",
    "4956": "光鋐",
    "4958": "臻鼎-KY",
    "4960": "誠美材",
    "4961": "天鈺",
    "4967": "十銓",
    "4968": "立積",
    "4976": "佳凌",
    "4977": "眾達-KY",
    "4989": "榮科",
    "4994": "傳奇",
    "4999": "鑫禾",
    "5007": "三星",
    "5203": "訊連",
    "5215": "科嘉-KY",
    "5222": "全訊",
    "5225": "東科-KY",
    "5234": "達興材料",
    "5243": "乙盛-KY",
    "5244": "弘凱",
    "5258": "虹堡",
    "5269": "祥碩",
    "5283": "禾聯碩",
    "5284": "jpp-KY",
    "5285": "界霖",
    "5288": "豐祥-KY",
    "5292": "華懋",
    "5306": "桂盟",
    "5388": "中磊",
    "5434": "崇越",
    "5469": "瀚宇博",
    "5471": "松翰",
    "5484": "慧友",
    "5515": "建國",
    "5519": "隆大",
    "5521": "工信",
    "5522": "遠雄",
    "5525": "順天",
    "5531": "鄉林",
    "5533": "皇鼎",
    "5534": "長虹",
    "5538": "東明-KY",
    "5546": "永固-KY",
    "5607": "遠雄港",
    "5608": "四維航",
    "5706": "鳳凰",
    "5871": "中租-KY",
    "5876": "上海商銀",
    "5880": "合庫金",
    "5906": "台南-KY",
    "5907": "大洋-KY",
    "6005": "群益證",
    "6024": "群益期",
    "6108": "競國",
    "6112": "邁達特",
    "6115": "鎰勝",
    "6116": "彩晶",
    "6117": "迎廣",
    "6120": "達運",
    "6128": "上福",
    "6133": "金橋",
    "6136": "富爾特",
    "6139": "亞翔",
    "6141": "柏承",
    "6142": "友勁",
    "6152": "百一",
    "6153": "嘉聯益",
    "6155": "鈞寶",
    "6164": "華興",
    "6165": "浪凡",
    "6166": "凌華",
    "6168": "宏齊",
    "6176": "瑞儀",
    "6177": "達麗",
    "6183": "關貿",
    "6184": "大豐電",
    "6189": "豐藝",
    "6191": "精成科",
    "6192": "巨路",
    "6196": "帆宣",
    "6197": "佳必琪",
    "6201": "亞弘電",
    "6202": "盛群",
    "6205": "詮欣",
    "6206": "飛捷",
    "6209": "今國光",
    "6213": "聯茂",
    "6214": "精誠",
    "6215": "和椿",
    "6216": "居易",
    "6224": "聚鼎",
    "6225": "天瀚",
    "6226": "光鼎",
    "6230": "尼得科超眾",
    "6235": "華孚",
    "6239": "力成",
    "6243": "迅杰",
    "6257": "矽格",
    "6269": "台郡",
    "6271": "同欣電",
    "6272": "驊陞",
    "6277": "宏正",
    "6278": "台表科",
    "6281": "全國電",
    "6282": "康舒",
    "6283": "淳安",
    "6285": "啟碁",
    "6405": "悅城",
    "6409": "旭隼",
    "6412": "群電",
    "6414": "樺漢",
    "6415": "矽力*-KY",
    "6416": "瑞祺電通",
    "6426": "統新",
    "6431": "光麗-KY",
    "6438": "迅得",
    "6442": "光聖",
    "6443": "元晶",
    "6446": "藥華藥",
    "6449": "鈺邦",
    "6451": "訊芯-KY",
    "6456": "GIS-KY",
    "6464": "台數科",
    "6472": "保瑞",
    "6477": "安集",
    "6491": "晶碩",
    "6504": "南六",
    "6505": "台塑化",
    "6515": "穎崴",
    "6525": "捷敏-KY",
    "6526": "達發",
    "6531": "愛普*",
    "6533": "晶心科",
    "6534": "正瀚-創",
    "6541": "泰福-KY",
    "6550": "北極星藥業-KY",
    "6552": "易華電",
    "6558": "興能高",
    "6573": "虹揚-KY",
    "6579": "研揚",
    "6581": "鋼聯",
    "6582": "申豐",
    "6585": "鼎基",
    "6589": "台康生技",
    "6591": "動力-KY",
    "6592": "和潤企業",
    "6598": "ABC-KY",
    "6605": "帝寶",
    "6606": "建德工業",
    "6614": "資拓宏宇",
    "6625": "必應",
    "6641": "基士德-KY",
    "6645": "金萬林-創",
    "6655": "科定",
    "6657": "華安",
    "6658": "聯策",
    "6666": "羅麗芬-KY",
    "6668": "中揚光",
    "6669": "緯穎",
    "6670": "復盛應用",
    "6671": "三能-KY",
    "6672": "騰輝電子-KY",
    "6674": "鋐寶科技",
    "6689": "伊雲谷",
    "6691": "洋基工程",
    "6695": "芯鼎",
    "6698": "旭暉應材",
    "6706": "惠特",
    "6715": "嘉基",
    "6719": "力智",
    "6722": "輝創",
    "6742": "澤米",
    "6743": "安普新",
    "6753": "龍德造船",
    "6754": "匯僑設計",
    "6756": "威鋒電子",
    "6757": "台灣虎航",
    "6768": "志強-KY",
    "6770": "力積電",
    "6771": "平和環保-創",
    "6776": "展碁國際",
    "6781": "AES-KY",
    "6782": "視陽",
    "6789": "采鈺",
    "6790": "永豐實",
    "6792": "詠業",
    "6794": "向榮生技",
    "6796": "晉弘",
    "6799": "來頡",
    "6805": "富世達",
    "6806": "森崴能源",
    "6807": "峰源-KY",
    "6830": "汎銓",
    "6831": "邁科",
    "6834": "天二科技",
    "6835": "圓裕",
    "6838": "台新藥",
    "6854": "錼創科技-KY創",
    "6861": "睿生光電",
    "6862": "三集瑞-KY",
    "6863": "永道-KY",
    "6869": "雲豹能源",
    "6873": "泓德能源",
    "6885": "全福生技",
    "6887": "寶綠特-KY",
    "6890": "來億-KY",
    "6901": "鑽石投資",
    "6902": "GOGOLOOK",
    "6906": "現觀科",
    "6909": "創控",
    "6914": "阜爾運通",
    "6916": "華凌",
    "6918": "愛派司",
    "6919": "康霈*",
    "6921": "嘉雨思-創",
    "6923": "中台",
    "6924": "榮惠-KY創",
    "6928": "攸泰科技",
    "6931": "青松健康",
    "6933": "AMAX-KY",
    "6934": "心誠鎂",
    "6936": "永鴻生技",
    "6937": "天虹",
    "6944": "兆聯實業",
    "6949": "沛爾生醫-創",
    "6951": "青新-創",
    "6952": "大武山",
    "6955": "邦睿生技-創",
    "6957": "裕慶-KY",
    "6958": "日盛台駿",
    "6962": "奕力-KY",
    "6965": "中傑-KY",
    "6969": "成信實業*-創",
    "6988": "威力暘-創",
    "6994": "富威電力",
    "7610": "聯友金屬-創",
    "7631": "聚賢研發-創",
    "7705": "三商餐飲",
    "7711": "永擎",
    "7721": "微程式",
    "7722": "LINEPAY",
    "7730": "暉盛-創",
    "7732": "金興精密",
    "7736": "虎山",
    "7740": "熙特爾-創",
    "7749": "意騰-KY",
    "7750": "新代",
    "7765": "中華資安",
    "7769": "鴻勁",
    "7780": "大研生醫*",
    "7786": "東方風能",
    "7788": "松川精密",
    "7791": "皇家可口",
    "7795": "長廣",
    "7799": "禾榮科",
    "7823": "奧義賽博-KY創",
    "8011": "台通",
    "8016": "矽創",
    "8021": "尖點",
    "8028": "昇陽半導體",
    "8033": "雷虎",
    "8039": "台虹",
    "8045": "達運光電",
    "8046": "南電",
    "8070": "長華*",
    "8072": "陞泰",
    "8081": "致新",
    "8101": "華冠",
    "8103": "瀚荃",
    "8104": "錸寶",
    "8105": "凌巨",
    "8110": "華東",
    "8112": "至上",
    "8114": "振樺電",
    "8131": "福懋科",
    "8150": "南茂",
    "8162": "微矽電子-創",
    "8163": "達方",
    "8201": "無敵",
    "8210": "勤誠",
    "8213": "志超",
    "8215": "明基材",
    "8222": "寶一",
    "8249": "菱光",
    "8261": "富鼎",
    "8271": "宇瞻",
    "8341": "日友",
    "8367": "建新國際",
    "8374": "羅昇",
    "8404": "百和興業-KY",
    "8411": "福貞-KY",
    "8422": "可寧衛*",
    "8429": "金麗-KY",
    "8438": "昶昕",
    "8442": "威宏-KY",
    "8443": "阿瘦",
    "8454": "富邦媒",
    "8462": "柏文",
    "8463": "潤泰材",
    "8464": "億豐",
    "8466": "美吉吉-KY",
    "8467": "波力-KY",
    "8473": "山林水",
    "8476": "台境*",
    "8478": "東哥遊艇",
    "8481": "政伸",
    "8482": "商億-KY",
    "8487": "愛爾達-創",
    "8488": "吉源-KY",
    "8499": "鼎炫-KY",
    "8926": "台汽電",
    "8940": "新天地",
    "8996": "高力",
    "9802": "鈺齊-KY",
    "9902": "台火",
    "9904": "寶成",
    "9905": "大華",
    "9906": "欣巴巴",
    "9907": "統一實",
    "9908": "大台北",
    "9910": "豐泰",
    "9911": "櫻花",
    "9912": "偉聯",
    "9914": "美利達",
    "9917": "中保科",
    "9918": "欣天然",
    "9919": "康那香",
    "9921": "巨大",
    "9924": "福興",
    "9925": "新保",
    "9926": "新海",
    "9927": "泰銘",
    "9928": "中視",
    "9929": "秋雨",
    "9930": "中聯資源",
    "9931": "欣高",
    "9933": "中鼎",
    "9934": "成霖",
    "9935": "慶豐富",
    "9937": "全國",
    "9938": "百和",
    "9939": "宏全",
    "9940": "信義",
    "9941": "裕融",
    "9942": "茂順",
    "9943": "好樂迪",
    "9944": "新麗",
    "9945": "潤泰新",
    "9946": "三發地產",
    "9955": "佳龍",
    "9958": "世紀鋼"
}
# ====== 上市股票清單（代碼 -> 名稱）======
# 此清單用於 Yahoo Finance 批次下載，定期更新
TWSE_STOCK_LIST = None  # 將在首次更新時從 Yahoo Finance 動態取得

def get_twse_stock_codes():
    """取得上市股票代碼清單
    
    優先使用內建清單（避免 Render 等海外環境被 TWSE 封鎖），
    將嘗試從 TWSE API 取得最新清單作為更新機制
    """
    global TWSE_STOCK_LIST
    
    # 如果已經有快取的清單，直接使用
    if TWSE_STOCK_LIST:
        return TWSE_STOCK_LIST
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # 嘗試從 TWSE API 取得最新股票清單（如果可用）
    twse_apis = [
        'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL',
        'https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL?response=json',
    ]
    
    for api_url in twse_apis:
        try:
            response = requests.get(api_url, headers=headers, timeout=10, verify=False)
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                continue  # 被封鎖，跳過
            
            raw_json = response.json()
            stock_list = {}
            
            if isinstance(raw_json, list):
                # openapi 格式
                for item in raw_json:
                    code = item.get('Code', '').strip()
                    name = item.get('Name', '').strip()
                    if code and len(code) == 4 and code.isdigit() and 1000 <= int(code) <= 9999:
                        if not any(kw in name for kw in ['DR', 'TDR', 'ETF', 'ETN', '權證', '特別股', '存託憑證']):
                            stock_list[code] = name
            elif isinstance(raw_json, dict) and raw_json.get('stat') == 'OK':
                # rwd 格式
                for row in raw_json.get('data', []):
                    if len(row) >= 2:
                        code = row[0].strip()
                        name = row[1].strip()
                        if code and len(code) == 4 and code.isdigit() and 1000 <= int(code) <= 9999:
                            if not any(kw in name for kw in ['DR', 'TDR', 'ETF', 'ETN', '權證', '特別股', '存託憑證']):
                                stock_list[code] = name
            
            if len(stock_list) > 500:
                TWSE_STOCK_LIST = stock_list
                logger.info(f"從 TWSE API 取得 {len(stock_list)} 支上市股票清單")
                return stock_list
        except Exception as e:
            logger.warning(f"從 TWSE API 取得股票清單失敗: {e}")
            continue
    
    # TWSE API 被封鎖或不可用，使用內建股票清單
    logger.info(f"使用內建上市股票清單（{len(BUILTIN_TWSE_STOCK_LIST)} 支）")
    TWSE_STOCK_LIST = BUILTIN_TWSE_STOCK_LIST.copy()
    return TWSE_STOCK_LIST

def discover_twse_stocks_via_yahoo():
    """透過 Yahoo Finance API 動態探測有效的上市股票代碼"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    # 產生常見的上市股票代碼範圍
    candidate_codes = []
    for i in range(1101, 9999):
        candidate_codes.append(str(i))
    
    valid_stocks = {}
    
    def check_stock(code):
        try:
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{code}.TW?interval=1d&range=1d'
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, headers=headers, timeout=5, verify=False)
            if r.status_code == 200:
                data = r.json()
                result = data.get('chart', {}).get('result', [None])[0]
                if result:
                    name = result.get('meta', {}).get('shortName', '')
                    symbol = result.get('meta', {}).get('symbol', '')
                    if symbol and name:
                        return (code, name)
            return None
        except:
            return None
    
    # 分批探測（每批 500 個代碼）
    batch_size = 500
    for i in range(0, len(candidate_codes), batch_size):
        batch = candidate_codes[i:i+batch_size]
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = {executor.submit(check_stock, code): code for code in batch}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    valid_stocks[result[0]] = result[1]
        
        if len(valid_stocks) > 800:  # 已找到足夠多的股票
            break
    
    logger.info(f"透過 Yahoo Finance 探測到 {len(valid_stocks)} 支上市股票")
    return valid_stocks

def fetch_single_stock_yahoo(code):
    """從 Yahoo Finance v8 chart API 取得單支上市股票的即時資料"""
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{code}.TW?interval=1d&range=2d'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=10, verify=False)
        if r.status_code != 200:
            return None
        
        data = r.json()
        chart_result = data.get('chart', {}).get('result', [None])[0]
        if not chart_result:
            return None
        
        meta = chart_result.get('meta', {})
        indicators = chart_result.get('indicators', {}).get('quote', [{}])[0]
        timestamps = chart_result.get('timestamp', [])
        
        if not timestamps or not indicators.get('close'):
            return None
        
        # 取最後一天的資料
        idx = -1
        close_price = indicators['close'][idx]
        open_price = indicators['open'][idx]
        high_price = indicators['high'][idx]
        low_price = indicators['low'][idx]
        volume = indicators['volume'][idx]
        
        if close_price is None or volume is None:
            return None
        
        # 計算漲跌（使用前一天收盤價）
        prev_close = meta.get('chartPreviousClose', close_price)
        if len(indicators['close']) >= 2 and indicators['close'][-2] is not None:
            prev_close = indicators['close'][-2]
        
        change = close_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close != 0 else 0
        
        # 取得交易日期（使用台灣時區）
        trade_date = datetime.fromtimestamp(timestamps[idx], tz=TW_TZ).strftime('%Y-%m-%d')
        
        # 取得股票名稱
        stock_name = meta.get('shortName', '') or meta.get('longName', '')
        
        return {
            'code': code,
            'name': stock_name,
            'close': float(close_price),
            'open': float(open_price) if open_price else float(close_price),
            'high': float(high_price) if high_price else float(close_price),
            'low': float(low_price) if low_price else float(close_price),
            'volume': int(volume),
            'change': float(change),
            'change_percent': float(change_pct),
            'date': trade_date,
            'market': 'TWSE'
        }
    except Exception as e:
        return None

def fetch_otc_stock_data():
    """獲取上市股票資料（使用 Yahoo Finance API）
    
    由於 TWSE API 封鎖海外伺服器 IP（如 Render），
    改用 Yahoo Finance v8 chart API 搭配並行請求取得所有上市股票資料。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    try:
        logger.info("開始獲取上市股票資料（Yahoo Finance API）...")
        
        # 取得上市股票代碼清單
        stock_list = get_twse_stock_codes()
        if not stock_list:
            logger.error("無法取得上市股票代碼清單")
            return None
        
        codes = list(stock_list.keys())
        logger.info(f"準備下載 {len(codes)} 支上市股票資料...")
        
        # 使用並行請求批次下載
        all_results = []
        failed_count = 0
        
        update_status['total'] = len(codes)
        update_status['progress'] = 0
        update_status['message'] = f'正在下載 {len(codes)} 支上市股票資料...'
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(fetch_single_stock_yahoo, code): code for code in codes}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    # 優先使用 TWSE 清單中的中文簡稱，Yahoo Finance 回傳的是英文名稱
                    if result['code'] in stock_list:
                        result['name'] = stock_list[result['code']]
                    all_results.append(result)
                else:
                    failed_count += 1
                
                # 更新進度
                update_status['progress'] = len(all_results) + failed_count
        
        if not all_results:
            logger.error("Yahoo Finance API 無法取得任何股票資料")
            return None
        
        logger.info(f"成功從 Yahoo Finance 取得 {len(all_results)} 支上市股票資料（失敗 {failed_count} 支）")
        return all_results
        
    except Exception as e:
        logger.error(f"從 Yahoo Finance 獲取上市股票資料時發生錯誤: {str(e)}")
        return None
def process_otc_stock_data(raw_data):
    """處理上市股票資料（從 Yahoo Finance API）
    
    raw_data 為 fetch_otc_stock_data 回傳的 list，每個元素已經是處理好的 dict 格式。
    """
    processed_stocks = {}
    current_date = None
    
    try:
        for item in raw_data:
            stock_code = item.get('code', '').strip()
            stock_name = item.get('name', '').strip()
            
            # 過濾條件：只處理上市股票（代碼1000-9999）
            if (stock_code and 
                len(stock_code) == 4 and 
                stock_code.isdigit() and
                1000 <= int(stock_code) <= 9999 and
                not any(keyword in stock_name for keyword in ['DR', 'TDR', 'ETF', 'ETN', '權證', '特別股', '存託憑證'])):
                
                try:
                    closing_price = float(item.get('close', 0))
                    opening_price = float(item.get('open', 0))
                    highest_price = float(item.get('high', 0))
                    lowest_price = float(item.get('low', 0))
                    trade_volume = int(item.get('volume', 0))
                    change = float(item.get('change', 0))
                    change_percent = float(item.get('change_percent', 0))
                    trade_date = item.get('date', '')
                    
                    # 過濾無效資料
                    if closing_price > 0 and trade_volume > 0:
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

def update_stocks_data_background():
    """後台執行的更新任務"""
    global stocks_data, last_update_time, data_date, update_status
    
    try:
        update_status['message'] = '正在取得上市股票清單...'
        logger.info("開始後台更新上市股票資料...")
        
        # 獲取上市股票資料
        raw_data = fetch_otc_stock_data()
        if not raw_data:
            logger.error("無法獲取上市股票資料")
            update_status['is_running'] = False
            update_status['success'] = False
            update_status['message'] = '無法獲取股票資料，請稍後再試'
            update_status['finished_at'] = get_taiwan_time().strftime('%Y-%m-%d %H:%M:%S')
            return
        
        update_status['message'] = '正在處理股票資料...'
        
        # 處理資料
        processed_data, current_date = process_otc_stock_data(raw_data)
        if not processed_data:
            logger.error("處理上市股票資料失敗")
            update_status['is_running'] = False
            update_status['success'] = False
            update_status['message'] = '處理股票資料失敗，請稍後再試'
            update_status['finished_at'] = get_taiwan_time().strftime('%Y-%m-%d %H:%M:%S')
            return
        
        # 更新全域變數
        stocks_data = processed_data
        data_date = current_date
        last_update_time = get_taiwan_time()
        
        update_status['is_running'] = False
        update_status['success'] = True
        update_status['message'] = f'成功更新 {len(stocks_data)} 支上市股票資料'
        update_status['finished_at'] = get_taiwan_time().strftime('%Y-%m-%d %H:%M:%S')
        
        logger.info(f"後台更新完成：{len(stocks_data)} 支上市股票資料，資料日期: {data_date}")
        
    except Exception as e:
        logger.error(f"後台更新上市股票資料時發生錯誤: {str(e)}")
        update_status['is_running'] = False
        update_status['success'] = False
        update_status['message'] = f'更新失敗: {str(e)}'
        update_status['finished_at'] = get_taiwan_time().strftime('%Y-%m-%d %H:%M:%S')

def update_stocks_data():
    """更新股票資料（直接同步版本，保留相容）"""
    global stocks_data, last_update_time, data_date
    
    try:
        logger.info("開始更新上市股票資料...")
        
        raw_data = fetch_otc_stock_data()
        if not raw_data:
            return False
        
        processed_data, current_date = process_otc_stock_data(raw_data)
        if not processed_data:
            return False
        
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
    """診斷端點：測試 Yahoo Finance API 和 TWSE API 的連線狀況"""
    import time as time_module
    import socket
    result = {
        'timestamp': get_taiwan_time().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': 'Yahoo Finance v8 chart API',
        'tests': {}
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    # 測試 Yahoo Finance API
    try:
        start = time_module.time()
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/2330.TW?interval=1d&range=1d'
        response = requests.get(url, headers=headers, timeout=15, verify=False)
        elapsed = time_module.time() - start
        
        if response.status_code == 200:
            data = response.json()
            chart_result = data.get('chart', {}).get('result', [None])[0]
            if chart_result:
                meta = chart_result.get('meta', {})
                result['tests']['yahoo_finance'] = {
                    'status': 'success',
                    'http_code': 200,
                    'elapsed_seconds': round(elapsed, 2),
                    'sample_stock': meta.get('symbol', ''),
                    'sample_price': meta.get('regularMarketPrice', 0)
                }
            else:
                result['tests']['yahoo_finance'] = {
                    'status': 'no_data',
                    'http_code': 200,
                    'elapsed_seconds': round(elapsed, 2)
                }
        else:
            result['tests']['yahoo_finance'] = {
                'status': 'failed',
                'http_code': response.status_code,
                'elapsed_seconds': round(elapsed, 2)
            }
    except Exception as e:
        result['tests']['yahoo_finance'] = {
            'status': 'error',
            'error': str(e),
            'error_type': type(e).__name__
        }
    
    # 測試 TWSE API（用於取得股票清單）
    twse_apis = [
        ('openapi_twse', 'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL'),
        ('twse_rwd', 'https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL?response=json'),
    ]
    
    for test_name, url in twse_apis:
        try:
            start = time_module.time()
            response = requests.get(url, headers=headers, timeout=15, verify=False)
            elapsed = time_module.time() - start
            content_type = response.headers.get('Content-Type', 'unknown')
            
            if 'text/html' in content_type:
                result['tests'][test_name] = {
                    'status': 'blocked',
                    'http_code': response.status_code,
                    'elapsed_seconds': round(elapsed, 2),
                    'note': 'TWSE 封鎖海外 IP，已改用 Yahoo Finance'
                }
            else:
                result['tests'][test_name] = {
                    'status': 'available',
                    'http_code': response.status_code,
                    'elapsed_seconds': round(elapsed, 2)
                }
        except Exception as e:
            result['tests'][test_name] = {
                'status': 'error',
                'error': str(e)
            }
    
    # 目前股票資料狀態
    result['stocks_data_count'] = len(stocks_data)
    result['data_date'] = data_date
    result['last_update'] = last_update_time.strftime('%Y-%m-%d %H:%M:%S') if last_update_time else None
    result['stock_list_cached'] = TWSE_STOCK_LIST is not None
    result['stock_list_count'] = len(TWSE_STOCK_LIST) if TWSE_STOCK_LIST else 0
    
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
            'version': '5.0 - TWSE Market Edition (Yahoo Finance)'
        })
    except Exception as e:
        logger.error(f"健康檢查失敗: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/update', methods=['POST'])
def update_data():
    """更新股票資料API（非同步版本）"""
    global update_status
    
    try:
        with update_lock:
            if update_status['is_running']:
                return jsonify({
                    'success': True,
                    'async': True,
                    'status': 'running',
                    'message': '更新已在進行中，請稍候...',
                    'progress': update_status['progress'],
                    'total': update_status['total']
                })
            
            # 重置狀態並啟動後台執行緒
            update_status['is_running'] = True
            update_status['success'] = None
            update_status['progress'] = 0
            update_status['total'] = 0
            update_status['message'] = '正在初始化...'
            update_status['started_at'] = get_taiwan_time().strftime('%Y-%m-%d %H:%M:%S')
            update_status['finished_at'] = None
        
        # 在後台執行緒中啟動更新
        thread = threading.Thread(target=update_stocks_data_background, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'async': True,
            'status': 'started',
            'message': '更新已在後台啟動，請稍候約 60-90 秒...'
        })
        
    except Exception as e:
        logger.error(f"更新API錯誤: {str(e)}")
        update_status['is_running'] = False
        return jsonify({
            'success': False,
            'message': f'更新失敗: {str(e)}'
        }), 500

@app.route('/api/update_status')
def get_update_status():
    """查詢更新進度"""
    try:
        last_update_str = None
        if last_update_time:
            last_update_str = last_update_time.strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'is_running': update_status['is_running'],
            'progress': update_status['progress'],
            'total': update_status['total'],
            'message': update_status['message'],
            'success': update_status['success'],
            'started_at': update_status['started_at'],
            'finished_at': update_status['finished_at'],
            'stocks_count': len(stocks_data),
            'data_date': data_date,
            'last_update': last_update_str
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

