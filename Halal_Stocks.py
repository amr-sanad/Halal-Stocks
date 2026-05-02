import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Halal Investment Decision Dashboard", layout="wide")

st.title("🕋 Halal Investment Decision Dashboard")

st.info(
    "Informational and research use only. Not financial or investment advice. "
    "Data sourced from Yahoo Finance via yfinance."
)

# --------------------------------------------------
# LOAD PORTFOLIO
# --------------------------------------------------
PORTFOLIO_FILE = "portfolio.xlsx"
portfolio_df = pd.read_excel(PORTFOLIO_FILE)
tickers = portfolio_df["Ticker"].dropna().str.upper().tolist()

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------
def get_financials(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    bs = stock.balance_sheet
    is_stmt = stock.financials
    hist = stock.history(period="1y")

    # --- Shariah-related ---
    assets = bs.loc['Total Assets'].iloc[0] if 'Total Assets' in bs.index else np.nan
    debt = bs.loc['Total Debt'].iloc[0] if 'Total Debt' in bs.index else 0
    revenue = is_stmt.loc['Total Revenue'].iloc[0] if 'Total Revenue' in is_stmt.index else np.nan
    interest_income = is_stmt.loc['Interest Income'].iloc[0] if 'Interest Income' in is_stmt.index else 0

    debt_assets = (debt / assets) * 100 if assets else np.nan
    impure_rev = (interest_income / revenue) * 100 if revenue else np.nan

    halal = (debt_assets < 33) and (impure_rev < 5)

    # --- Price & trend ---
    current_price = info.get("currentPrice", np.nan)
    high_52w = info.get("fiftyTwoWeekHigh", np.nan)
    low_52w = info.get("fiftyTwoWeekLow", np.nan)

    upside_52w = ((high_52w - current_price) / current_price) * 100 if current_price else np.nan
    range_position = (
        (current_price - low_52w) / (high_52w - low_52w) * 100
        if high_52w and low_52w and high_52w != low_52w
        else np.nan
    )

    ma_200 = hist["Close"].rolling(200).mean().iloc[-1] if len(hist) >= 200 else np.nan
    above_200dma = current_price > ma_200 if pd.notna(ma_200) else False

    # --- Valuation & quality ---
    forward_pe = info.get("forwardPE", np.nan)
    peg = info.get("pegRatio", np.nan)
    roe = info.get("returnOnEquity", np.nan)
    roe_pct = roe * 100 if pd.notna(roe) else np.nan

    # --- Buy Score (objective, free) ---
    buy_score = 0
    buy_score += 1 if above_200dma else 0
    buy_score += 1 if upside_52w and upside_52w > 15 else 0
    buy_score += 1 if peg and peg < 1.5 else 0
    buy_score += 1 if roe_pct and roe_pct > 10 else 0

    return {
        "Ticker": ticker,
        "Halal Status": "✅ COMPLIANT" if halal else "❌ NON‑COMPLIANT",
        "Debt / Assets %": round(debt_assets, 1),
        "Impure Revenue %": round(impure_rev, 1),
        "Current Price": round(current_price, 2),
        "52W High": round(high_52w, 2),
        "Upside to 52W High %": round(upside_52w, 1),
        "Above 200DMA": "✅" if above_200dma else "❌",
        "52W Range Position %": round(range_position, 1),
        "Forward P/E": round(forward_pe, 1) if pd.notna(forward_pe) else None,
        "PEG": round(peg, 2) if pd.notna(peg) else None,
        "ROE %": round(roe_pct, 1),
        "Buy Score (0–4)": buy_score,
    }

# --------------------------------------------------
# RUN ANALYSIS
# --------------------------------------------------
if st.button("Run Portfolio Analysis"):
    results = []

    for ticker in tickers:
        with st.spinner(f"Analyzing {ticker}..."):
            try:
                results.append(get_financials(ticker))
            except Exception as e:
                st.error(f"{ticker}: {e}")

    df = pd.DataFrame(results)
    st.dataframe(df, use_container_width=True)

    df.to_excel("latest_results.xlsx", index=False)
    st.success("✅ Analysis complete — saved to latest_results.xlsx")

# --------------------------------------------------
# INTERPRETATION GUIDE
# --------------------------------------------------
with st.expander("📘 How to interpret the Buy Score"):
    st.markdown("""
**Buy Score (0–4)** is a decision‑support metric, not a command.

**+1 point each for:**
- Price above 200‑day moving average (trend positive)
- Upside to 52‑week high > 15%
- PEG ratio < 1.5 (reasonable growth valuation)
- ROE > 10% (business quality)

**Typical actions:**
- **0–1** → Avoid / Monitor
- **2** → Neutral / Watch
- **3** → Attractive
- **4** → Strong candidate (if halal)
""")

# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<small>"
    "Data source: Yahoo Finance via yfinance. "
    "This tool is for educational and personal research use only."
    "</small>",
    unsafe_allow_html=True
)
