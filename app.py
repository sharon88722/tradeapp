import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import requests

# ==========================================
# 1. PWA 配置與頁面設定
# ==========================================
st.set_page_config(
    page_title="網格交易回測 PWA",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

pwa_meta_tags = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
"""
st.markdown(pwa_meta_tags, unsafe_allow_html=True)

# ==========================================
# 2. 字型處理
# ==========================================
@st.cache_resource
def get_chinese_font():
    font_path = "NotoSansTC-Regular.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/ofl/notosanstc/NotoSansTC-Regular.ttf"
        try:
            r = requests.get(url, allow_redirects=True)
            r.raise_for_status()
            with open(font_path, 'wb') as f:
                f.write(r.content)
        except Exception:
            return None
    return fm.FontProperties(fname=font_path)

font_prop = get_chinese_font()

# ==========================================
# 3. 側邊欄設定
# ==========================================
st.sidebar.title("🛠️ 交易參數設定")

# 增加一點提示，讓使用者知道可以試試別的
stock_id = st.sidebar.text_input("股票代碼", "2330.TW", help="如果台股抓不到，試試看 'AAPL' 確認是否為網路問題")

period_options = {"1個月": "1mo", "3個月": "3mo", "6個月": "6mo", "1年": "1y"}
selected_period_label = st.sidebar.selectbox("回測期間", list(period_options.keys()), index=2)
period = period_options[selected_period_label]
grid_count = st.sidebar.slider("網格數量 (條)", min_value=3, max_value=20, value=10)

# ==========================================
# 4. 核心邏輯 (修正版：使用 history 方法)
# ==========================================
@st.cache_data(ttl=3600)
def load_data(symbol, time_period):
    try:
        # 使用 Ticker.history 替代 download，這在單一股票抓取時更穩定
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=time_period)
        
        if df.empty:
            return None
            
        # 只要 Close 欄位
        df = df[['Close']].copy()
        
        # 移除時區資訊 (Matplotlib 有時會因為時區報錯)
        df.index = df.index.tz_localize(None)
        
        return df
    except Exception as e:
        print(f"Error downloading {symbol}: {e}")
        return None

def calculate_signals(df, grid_num):
    high_price = df['Close'].max()
    low_price = df['Close'].min()
    
    if high_price == low_price:
        return [], [], []

    grids = np.linspace(low_price, high_price, grid_num + 2)[1:-1]
    
    buy_signals = []
    sell_signals = []
    prices = df['Close'].values
    dates = df.index
    
    for i in range(1, len(prices)):
        prev = prices[i-1]
        curr = prices[i]
        date = dates[i]
        
        for g in grids:
            if prev > g and curr <= g:
                buy_signals.append((date, curr))
            if prev < g and curr >= g:
                sell_signals.append((date, curr))
                
    return grids, buy_signals, sell_signals

# ==========================================
# 5. 主畫面執行
# ==========================================
st.title(f"📈 {stock_id} 網格交易回測")

# 顯示目前的 yfinance 版本，方便除錯
import yfinance
st.caption(f"Yfinance Version: {yfinance.__version__}")

with st.spinner('正在抓取股價資料...'):
    df = load_data(stock_id, period)

if df is None:
    st.error(f"❌ 找不到 {stock_id} 的資料。")
    st.info("💡 建議嘗試以下步驟解決：\n1. 確認代碼是否正確 (例如 2330.TW)。\n2. 嘗試輸入美股代碼 (如 AAPL) 測試，如果美股可以但台股不行，代表 Yahoo Finance 暫時擋住了該伺服器對台股的請求。")
else:
    grids, buys, sells = calculate_signals(df, grid_count)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("區間最高價", f"{df['Close'].max():.2f}")
    col1.metric("區間最低價", f"{df['Close'].min():.2f}")
    col2.metric("總買入次數", f"{len(buys)} 次")
    col2.metric("總賣出次數", f"{len(sells)} 次")
    
    if len(grids) > 1:
        col3.metric("網格間距", f"{(grids[1]-grids[0]):.2f} 元")

    # 繪圖
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.plot(df.index, df['Close'], label='收盤價', color='royalblue', linewidth=2, alpha=0.8)
    
    for g in grids:
        ax.axhline(y=g, color='gray', linestyle='--', linewidth=0.8, alpha=0.6)
        
    if buys:
        b_dates, b_prices = zip(*buys)
        ax.scatter(b_dates, b_prices, marker='^', color='green', s=150, label='買入訊號', zorder=5)
    
    if sells:
        s_dates, s_prices = zip(*sells)
        ax.scatter(s_dates, s_prices, marker='v', color='red', s=150, label='賣出訊號', zorder=5)
    
    ax.set_title(f'{stock_id} 網格交易回測', fontproperties=font_prop, fontsize=24)
    ax.set_xlabel('日期', fontproperties=font_prop, fontsize=16)
    ax.set_ylabel('股價 (TWD)', fontproperties=font_prop, fontsize=16)
    ax.legend(prop=font_prop, loc='best', fontsize=14)
    ax.grid(True, alpha=0.3)
    
    st.pyplot(fig)
    
    with st.expander("查看詳細交易訊號列表"):
        signal_data = []
        for d, p in buys:
            signal_data.append({"日期": d.strftime('%Y-%m-%d'), "價格": f"{p:.2f}", "動作": "買入 (Buy)"})
        for d, p in sells:
            signal_data.append({"日期": d.strftime('%Y-%m-%d'), "價格": f"{p:.2f}", "動作": "賣出 (Sell)"})
            
        if signal_data:
            df_signals = pd.DataFrame(signal_data).sort_values("日期")
            st.table(df_signals)
        else:
            st.write("此區間無觸發交易訊號。")
