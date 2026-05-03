import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import time

# --- 1. CONFIGURATION & HELPERS ---
st.set_page_config(page_title="Global Financial Analyser", layout="wide")

def safe_float(value):
    try:
        if value is None or pd.isna(value):
            return None
        f_val = float(value)
        return f_val if np.isfinite(f_val) else None
    except:
        return None

def format_large_num(value):
    num = safe_float(value)
    if num is None:
        return "N/A"
    if abs(num) >= 1e9:
        return f"{num/1e9:,.2f}B"
    if abs(num) >= 1e6:
        return f"{num/1e6:,.2f}M"
    return f"{num:,.2f}"

def safe_round(value, decimals=2):
    num = safe_float(value)
    return round(num, decimals) if num is not None else "N/A"

def create_table_image(df):
    """Generates a high-res PNG of the results table."""
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

# --- 2. CACHED DATA FETCHING ---
# TTL is set to 12 hours (43,200 seconds)
@st.cache_data(ttl=43200)
def get_financial_metrics(ticker_symbol):
    # yfinance 0.2.54+ handles browser impersonation internally
    stock = yf.Ticker(ticker_symbol)
    
    # Wake up the API
    _ = stock.history(period="1mo")
    info = stock.info
    
    # Secure dividend access
    try:
        actions = stock.actions
        divs = actions['Dividends'] if not actions.empty and 'Dividends' in actions.columns else pd.Series(dtype=float)
    except:
        divs = pd.Series(dtype=float)
    
    price = safe_float(info.get("currentPrice") or info.get("previousClose"))
    if not price:
        hist = stock.history(period="1d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
        else:
            raise ValueError("Price Unavailable")

    # TTM Dividend Logic (Trailing 12 Months)
    now = pd.Timestamp.now(tz='UTC')
    ttm_sum = divs[divs.index > (now - pd.DateOffset(years=1))].sum() if not divs.empty else 0
    y1_sum = divs[(divs.index <= (now - pd.DateOffset(years=1))) & (divs.index > (now - pd.DateOffset(years=2)))].sum() if not divs.empty else 0
    y3_sum = divs[(divs.index <= (now - pd.DateOffset(years=3))) & (divs.index > (now - pd.DateOffset(years=4)))].sum() if not divs.empty else 0

    denom = price / 100 if ticker_symbol.endswith(".L") and price > 10 else price
    manual_yield = (ttm_sum / denom) * 100 if denom > 0 else

