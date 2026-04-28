import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import time

# --- 1. SETTINGS & HELPERS ---
st.set_page_config(page_title="Global Financial Analyser", layout="wide")

def safe_float(value):
    try:
        if value is None or pd.isna(value): return None
        f_val = float(value)
        return f_val if np.isfinite(f_val) else None
    except: return None

def format_large_num(value):
    num = safe_float(value)
    if num is None: return "N/A"
    if abs(num) >= 1e9: return f"{num/1e9:,.2f}B"
    if abs(num) >= 1e6: return f"{num/1e6:,.2f}M"
    return f"{num:,.2f}"

def safe_round(value, decimals=2):
    num = safe_float(value)
    return round(num, decimals) if num is not None else "N/A"

def create_table_image(df):
    fig, ax = plt.subplots(figsize=(max(10, len(df.columns)*1.5), 5))
    ax.axis('off')
    tbl = ax.table(cellText=df.values, colLabels=df.columns, rowLabels=df.index, loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1.2, 2.5)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight', dpi=300)
    buf.seek(0)
    return buf

# --- 2. THE DATA ENGINE ---
@st.cache_data(ttl=43200)
def get_financial_metrics(ticker_symbol):
    stock = yf.Ticker(ticker_symbol)
    
    # Force metadata fetch
    info = stock.info
    
    # --- MULTI-STAGE PRICE FETCH (Fallback Logic) ---
    price = safe_float(info.get("currentPrice") or info.get("previousClose") or info.get("regularMarketPrice"))
    
    if not price:
        # Try history as a fallback
        hist = stock.history(period="5d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
        else:
            raise ValueError("Price Unavailable - Check Ticker Suffix")

    # Safe Dividend Access
    try:
        actions = stock.actions
        divs = actions['Dividends'] if not actions.empty and 'Dividends' in actions.columns else pd.Series(dtype=float)
    except:
        divs = pd.Series(dtype=float)
    
    # TTM Dividend Logic
    now = pd.Timestamp.now(tz='UTC')
    ttm_sum = divs[divs.index > (now - pd.DateOffset(years=1))].sum() if not divs.empty else 0
    y1_sum = divs[(divs.index <= (now - pd.DateOffset(years=1))) & (divs.index > (now - pd.DateOffset(years=2)))].sum() if not divs.empty else 0
    y3_sum = divs[(divs.index <= (now - pd.DateOffset(years=3))) & (divs.index > (now - pd.DateOffset(years=4)))].sum() if not divs.empty else 0

    # LSE Correction
    denom = price / 100 if ticker_symbol.endswith(".L") and price > 10 else price
    manual_yield = (ttm_sum / denom) * 100 if denom > 0 else 0

    pe_val = safe_float(info.get("trailingPE"))
    
    data = {
        "Ticker": ticker_symbol,
        "Market Cap": format_large_num(info.get("marketCap")),
        "Net Debt": format_large_num((info.get("totalDebt", 0) or 0) - (info.get("totalCash", 0) or 0)),
        "PE Ratio": safe_round(pe_val) if (pe_val and pe_val > 0) else "Neg. EPS",
        "Div Yield (%)": safe_round(manual_yield)
    }

    # Growth Logic
    income = stock.financials
    if not income.empty and 'Diluted EPS' in income.index:
        eps = income.loc['Diluted EPS'].dropna()
        if len(eps) >= 2:
            v_curr, v_prev = safe_float(eps.iloc[0]), safe_float(eps.iloc[1])
            if v_curr is not None and v_prev and v_prev != 0:
                data["EPS Gth 1yr %"] = safe_round(((v_curr / v_prev) - 1) * 100)
        if len(eps) >= 4:
            v_curr, v_old = safe_float(eps.iloc[0]), safe_float(eps.iloc[3])
            if v_curr is not None and v_old and v_old > 0:
                data["EPS Gth 3yr %"] = safe_round(((v_curr / v_old)**(1/3) - 1) * 100)

    if ttm_sum > 0:
        if y1_sum > 0: data["DPS Gth 1yr %"] = safe_round(((ttm_sum / y1_sum) - 1) * 100)
        if y3_sum > 0: data["DPS Gth 3yr %"] = safe_round(((ttm_sum / y3_sum)**(1/3) - 1) * 100)

    return data

# --- 3. INTERFACE ---
st.title("📊 Global Stock Fundamental Analyser")

c1, c2 = st.columns(2)
with c1:
    market = st.selectbox("Select Market", ["Australia (ASX)", "United Kingdom (LSE)", "USA", "Manual (Suffix included in code)"])
with c2:
    input_text = st.text_input("Enter Ticker Codes (comma separated)", value="GOOGL, WISE.L, FMG.AX, WTL.AX, TPC.AX")

# Logic to clean tickers and apply suffixes correctly
if st.button("Analyse Stocks"):
    suffix_map = {"Australia (ASX)": ".AX", "United Kingdom (LSE)": ".L", "USA": "", "Manual (Suffix included in code)": ""}
    target_suffix = suffix_map[market]
    
    raw_list = [t.strip().upper() for t in input_text.split(",") if t.strip()]
    
    processed_tickers = []
    for t in raw_list:
        # Strip existing suffixes to prevent BHP.AX.AX
        base = t.split(".")[0]
        # If user selected Manual or typed a suffix manually, prioritize that
        if "." in t:
            processed_tickers.append(t)
        else:
            processed_tickers.append(base + target_suffix)
    
    results = []
    progress_bar = st.progress(0)
    
    with st.spinner("Fetching data..."):
        for i, t in enumerate(processed_tickers):
            try:
                progress_bar.progress((i + 1) / len(processed_tickers))
                results.append(get_financial_metrics(t))
                time.sleep(1.0) # Compliance delay
            except Exception as e:
                st.warning(f"Could not retrieve {t}: {str(e)}")
    
    if results:
        df = pd.DataFrame(results).set_index("Ticker").T
        st.dataframe(df, use_container_width=True)
        st.divider()
        img_buf = create_table_image(df)
        st.download_button(label="📩 Download Table as Image", data=img_buf, file_name="stock_analysis.png", mime="image/png")


