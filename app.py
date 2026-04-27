import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- Helper Functions (Previously Working Logic) ---
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

def get_financial_metrics(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    # ... [Insert your working get_financial_metrics logic here] ...
    # Ensure it uses the 'safe_float' and 'format_large_num' functions defined above
    return {"Ticker": ticker, "Market Cap": format_large_num(info.get("marketCap"))} # Simplified for example

# --- Streamlit Web Interface ---
st.set_page_config(page_title="Global Stock Analyser", layout="wide")
st.title("📈 Global Financial Stock Analyser")

# Sidebar for Country Selection
st.sidebar.header("Settings")
country = st.sidebar.selectbox("Select Target Market", ["Australia (ASX)", "United Kingdom (LSE)", "USA (NYSE/NASDAQ)", "Manual Suffix"])

# Text Input for Stock Codes
raw_input = st.text_input("Enter Stock Codes (comma separated, e.g. CBA, WBC, BP)", value="CBA, BP")

# Mapping Logic
suffix_map = {"Australia (ASX)": ".AX", "United Kingdom (LSE)": ".L", "USA (NYSE/NASDAQ)": "", "Manual Suffix": ""}
suffix = suffix_map[country]

if st.button("Analyse Stocks"):
    # Clean and append suffixes
    tickers = [t.strip().upper() + suffix for t in raw_input.split(",") if t.strip()]
    
    with st.spinner(f"Fetching data for {len(tickers)} stocks..."):
        results = []
        for t in tickers:
            try:
                data = get_financial_metrics(t)
                results.append(data)
            except:
                st.error(f"Could not find data for {t}")
        
        if results:
            df = pd.DataFrame(results).set_index("Ticker").T
            st.dataframe(df, use_container_width=True)