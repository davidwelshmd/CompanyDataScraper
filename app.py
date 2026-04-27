import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# --- 1. CONFIGURATION & SESSION ---
st.set_page_config(page_title="Global Stock Analyser", layout="wide")

# Setup a session with a browser-like header to prevent being blocked
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

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

def get_financial_metrics(ticker_symbol):
    # Initialize ticker with our session
    stock = yf.Ticker(ticker_symbol, session=session)
    
    # FORCE-FETCH: Requesting history often 'wakes up' the API for small caps
    _ = stock.history(period="5d")
    info = stock.info
    
    # Try to find a price even if .info fails
    price = safe_float(info.get("currentPrice") or info.get("previousClose"))
    if not price:
        hist = stock.history(period="1d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
        else:
            raise ValueError("No price available")

    # Manual Yield Calculation
    divs = stock.dividends
    manual_yield = 0
    if not divs.empty and price > 0:
        last_year_divs = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.DateOffset(years=1))].sum()
        # LSE Correction (Pence vs Pounds)
        if ticker_symbol.endswith(".L") and price > 10: 
             manual_yield = (last_year_divs / (price / 100)) * 100
        else:
             manual_yield = (last_year_divs / price) * 100

    pe_val = safe_float(info.get("trailingPE"))
    
    data = {
        "Ticker": ticker_symbol,
        "Market Cap": format_large_num(info.get("marketCap")),
        "Net Debt": format_large_num((info.get("totalDebt", 0) or 0) - (info.get("totalCash", 0) or 0)),
        "PE Ratio": safe_round(pe_val) if (pe_val and pe_val > 0) else "Neg. EPS",
        "Div Yield (%)": safe_round(manual_yield)
    }

    # EPS & DPS Growth Logic (CAGR)
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

    if not divs.empty:
        annual_divs = divs.resample('YE').sum()
        if len(annual_divs) >= 2:
            d_curr, d_prev = safe_float(annual_divs.iloc[-1]), safe_float(annual_divs.iloc[-2])
            if d_curr is not None and d_prev and d_prev > 0:
                data["DPS Gth 1yr %"] = safe_round(((d_curr / d_prev) - 1) * 100)
        if len(annual_divs) >= 4:
            d_curr, d_old = safe_float(annual_divs.iloc[-1]), safe_float(annual_divs.iloc[-4])
            if d_curr is not None and d_old and d_old > 0:
                data["DPS Gth 3yr %"] = safe_round(((d_curr / d_old)**(1/3) - 1) * 100)

    return data

# --- 2. STREAMLIT INTERFACE ---
st.title("📊 Global Stock Fundamental Analyser")
st.markdown("Enter stock tickers and select the market to view key financial metrics and growth.")

c1, c2 = st.columns([1, 2])
with c1:
    market = st.selectbox("Select Market", ["Australia (ASX)", "United Kingdom (LSE)", "USA", "Manual"])
with c2:
    input_text = st.text_input("Enter Ticker Codes (comma separated)", value="BHP, CBA, WTL")

# Map Market Suffixes
suffix_map = {"Australia (ASX)": ".AX", "United Kingdom (LSE)": ".L", "USA": "", "Manual": ""}
target_suffix = suffix_map[market]

if st.button("Analyse Stocks"):
    # Clean input and handle potential double suffixes
    raw_list = [t.strip().upper() for t in input_text.split(",") if t.strip()]
    processed_tickers = []
    for t in raw_list:
        clean_t = t.replace(".AX", "").replace(".L", "") + target_suffix
        processed_tickers.append(clean_t)
    
    results = []
    with st.spinner("Accessing financial records..."):
        for t in processed_tickers:
            try:
                results.append(get_financial_metrics(t))
            except Exception as e:
                st.warning(f"Could not retrieve {t}. (Reason: {str(e)})")
    
    if results:
        df = pd.DataFrame(results).set_index("Ticker").T
        st.dataframe(df, use_container_width=True)
    else:
        st.error("No data found. Check your ticker codes or internet connection.")
