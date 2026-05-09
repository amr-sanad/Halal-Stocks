import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# --------------------------------------------------
# PAGE SETUP
# --------------------------------------------------
st.set_page_config(
    page_title="Consensus Shariah Screening & Decision Tool",
    layout="wide"
)

st.title("🕋 Consensus Shariah Screening & Decision Tool")

st.info(
    "Informational and research use only. "
    "Not financial, investment, or religious advice. "
    "Data sourced from Yahoo Finance via yfinance."
)

# --------------------------------------------------
# LOAD PORTFOLIO
# --------------------------------------------------
portfolio_df = pd.read_csv("portfolio.csv")
tickers = portfolio_df["Ticker"].dropna().str.upper().tolist()

# --------------------------------------------------
# ADR MAP
# --------------------------------------------------
ADR_MAP = {
    "IFX.DE": "IFNNY",
    "LONN.SW": "LZAGY",
    "HOLN.SW": "HCMLY",
    "ENGI.PA": "ENGIY",
    "SAN.PA": "SNY",
    "ADS.DE": "ADDYY",
}

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def first_existing(df, labels):
    for lbl in labels:
        if lbl in df.index:
            return df.loc[lbl].iloc[0]
    return np.nan

def safe_ratio(num, den):
    if pd.isna(num) or pd.isna(den) or den == 0:
        return np.nan
    return (num / den) * 100

# --------------------------------------------------
# ANALYSIS
# --------------------------------------------------
def analyze_ticker(ticker):

    try:
        fundamental_ticker = ADR_MAP.get(ticker, ticker)
        uses_adr = fundamental_ticker != ticker

        stock = yf.Ticker(fundamental_ticker)
        price_stock = yf.Ticker(ticker)

        # ---- SAFE INFO ----
        try:
            fast = stock.fast_info
        except:
            fast = {}

        # ---- COMPANY NAME ----
        try:
            info = stock.get_info()
            company_name = info.get("longName", ticker)
        except:
            company_name = ticker

        bs = stock.balance_sheet
        is_stmt = stock.financials

        # ---- Financials ----
        assets = first_existing(bs, ["Total Assets"])
        debt = first_existing(bs, ["Total Debt", "Long Term Debt", "Total Liab"])
        revenue = first_existing(is_stmt, ["Total Revenue", "Revenue"])
        interest = first_existing(
            is_stmt, ["Interest Income", "Interest and Investment Income"]
        )

        if pd.notna(revenue) and pd.isna(interest):
            interest = 0.0

        # ✅ ---- MARKET CAP FIX ----
        hist_price_short = price_stock.history(period="5d")

        if not hist_price_short.empty:
            last_price = hist_price_short["Close"].iloc[-1]
        else:
            last_price = np.nan

        shares = fast.get("shares", np.nan)

        if pd.notna(fast.get("market_cap")):
            spot_mcap = fast.get("market_cap")
        elif pd.notna(last_price) and pd.notna(shares):
            spot_mcap = last_price * shares
        else:
            spot_mcap = np.nan

        # ---- Avg market cap ----
        hist_mc = stock.history(period="2y", interval="1mo")

        avg_mcap = (
            hist_mc["Close"].mean() * shares
            if not hist_mc.empty and pd.notna(shares)
            else np.nan
        )

        # ---- Ratios ----
        debt_assets = safe_ratio(debt, assets)
        debt_spot = safe_ratio(debt, spot_mcap)
        debt_avg = safe_ratio(debt, avg_mcap)
        impure = safe_ratio(interest, revenue)

        def check(val, limit):
            return True if pd.notna(val) and val < limit else False if pd.notna(val) else None

        spot_ok = check(debt_spot, 30) and check(impure, 5)
        avg_ok = check(debt_avg, 30) and check(impure, 5)
        msci_ok = check(debt_assets, 33) and check(impure, 5)

        def disp(ok, val):
            if ok is None:
                return "⚠️ Data unavailable"
            return f"{'✅' if ok else '❌'} ({val:.1f}%)"

        checks = [spot_ok, avg_ok, msci_ok]
        if any(v is False for v in checks if v is not None):
            consensus = "❌ NON‑COMPLIANT"
        elif any(v is True for v in checks):
            consensus = "✅ COMPLIANT"
        else:
            consensus = "⚠️ INCONCLUSIVE"

        # ---- Price ----
        hist_price = price_stock.history(period="1y")

        if hist_price.empty:
            current_price = np.nan
            high_52w = np.nan
        else:
            current_price = hist_price["Close"].iloc[-1]
            high_52w = hist_price["Close"].max()

        upside_52w = (
            (high_52w - current_price) / current_price * 100
            if pd.notna(current_price)
            else np.nan
        )

        ma_200 = hist_price["Close"].rolling(200).mean().iloc[-1] if len(hist_price) >= 200 else np.nan
        above_200dma = current_price > ma_200 if pd.notna(ma_200) else False

        peg = fast.get("peg_ratio", np.nan)
        roe = fast.get("return_on_equity", np.nan)

        buy_score = sum([
            above_200dma,
            pd.notna(upside_52w) and upside_52w > 15,
            pd.notna(peg) and peg < 1.5,
            pd.notna(roe) and roe > 0.10
        ])

        # ✅ Rate limit protection
        time.sleep(1)

        return {
            "Ticker": ticker,
            "Company Name": company_name,
            "AAOIFI (Spot)": disp(spot_ok, debt_spot),
            "AAOIFI (24m Avg)": disp(avg_ok, debt_avg),
            "MSCI (Asset)": disp(msci_ok, debt_assets),
            "Impure Revenue %": None if pd.isna(impure) else round(impure, 1),
            "Consensus": consensus,
            "Current Price": round(current_price, 2) if pd.notna(current_price) else None,
            "Upside to 52W High %": None if pd.isna(upside_52w) else round(upside_52w, 1),
            "Above 200DMA": "✅" if above_200dma else "❌",
            "Buy Score (0–4)": int(buy_score),
            "ADR Used for Ratios": "Yes" if uses_adr else "No",
        }

    except Exception as e:
        return {
            "Ticker": ticker,
            "Company Name": "ERROR",
            "AAOIFI (Spot)": "❌",
            "AAOIFI (24m Avg)": "❌",
            "MSCI (Asset)": "❌",
            "Impure Revenue %": None,
            "Consensus": "❌ ERROR",
            "Current Price": None,
            "Upside to 52W High %": None,
            "Above 200DMA": "❌",
            "Buy Score (0–4)": 0,
            "ADR Used for Ratios": "No",
        }

# --------------------------------------------------
# RUN
# --------------------------------------------------
if st.button("Run Full Analysis"):

    results = []

    for t in tickers:
        st.write(f"Processing {t}...")
        results.append(analyze_ticker(t))

    df = pd.DataFrame(results)

    st.dataframe(df, use_container_width=True)

    df.to_csv("latest_results.csv", index=False)

    st.success("✅ Analysis completed")

# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<small>"
    "ADR financials are used when mapped. "
    "Market data © Yahoo Finance (via yfinance). "
    "For personal and educational use only."
    "</small>",
    unsafe_allow_html=True
        )
