import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Global Stock Analyser", layout="wide")

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
    stock = yf.Ticker(ticker_symbol)
    
    # Force-fetch metadata
    _ = stock.history(period="5d")
    info = stock.info
    
    # Price Check
    price = safe_float(info.get("currentPrice") or info.get("previousClose"))
    if not price:
        hist = stock.history(period="1d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
        else:
            raise ValueError("No price available")

    # Yield Calculation
    divs = stock.dividends
    manual_yield = 0
    if not divs.empty and price > 0:
        last_year_divs = divs[divs.index > (pd.Timestamp.now(tz='UTC') - pd.DateOffset(years=1))].sum()
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

# --- 2. INTERFACE ---
st.title("📊 Global Stock Analyser")

# FIXED: Added the number 2 to specify two columns
c1, c2 = st.columns(2) 

with c1:
    market = st.selectbox("Select Market", ["Australia (ASX)", "United Kingdom (LSE)", "USA", "Manual"])
with c2:
    input_text = st.text_input("Enter Ticker Codes", value="BHP, CBA, WTL")

suffix_map = {"Australia (ASX)": ".AX", "United Kingdom (LSE)": ".L", "USA": "", "Manual": ""}
target_suffix = suffix_map[market]

if st.button("Analyse Stocks"):
    raw_list = [t.strip().upper() for t in input_text.split(",") if t.strip()]
    processed_tickers = [t.replace(".AX", "").replace(".L", "") + target_suffix for t in raw_list]
    
    results = []
    with st.spinner("Fetching data..."):
        for t in processed_tickers:
            try:
                results.append(get_financial_metrics(t))
            except Exception as e:
                st.warning(f"Could not retrieve {t}: {str(e)}")
    
    if results:
        df = pd.DataFrame(results).set_index("Ticker").T
        st.dataframe(df, use_container_width=True)
