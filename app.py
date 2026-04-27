import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests

# 1. Setup Session for better reliability
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

def get_financial_metrics(ticker_symbol):
    stock = yf.Ticker(ticker_symbol, session=session)
    
    # --- CRITICAL FIX FOR SMALL CAPS ---
    # Attempt to force-load data by downloading history first
    _ = stock.history(period="1d") 
    info = stock.info
    
    # If info is still empty, try to get basic price from history
    price = safe_float(info.get("currentPrice") or info.get("previousClose"))
    if not price:
        hist = stock.history(period="5d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
        else:
            raise ValueError("No price data available")

    # 2. Basic Metrics
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

    # ... [Keep your EPS/DPS Growth logic here] ...
    return data
