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
        debt = first_existing(bs, ["Total Debt", "Long Term Debt"]) # Excluded Total Liab to remove non-debt items
        revenue = first_existing(is_stmt, ["Total Revenue", "Revenue"])
        interest = first_existing(
            is_stmt, ["Interest Income", "Interest and Investment Income"]
        )

        if pd.notna(revenue) and pd.isna(interest):
            interest = 0.0

        # ✅ OPTIMIZED HISTORICAL FETCH (Single combined request)
        hist_price = price_stock.history(period="2y") # 2 years historical data
        
        if not hist_price.empty:
            current_price = hist_price["Close"].iloc[-1]
            high_52w = hist_price["Close"].max()
            ma_200 = hist_price["Close"].rolling(200).mean().iloc[-1] if len(hist_price) >= 200 else np.nan
            
            # 24-Month Monthly Average Calculation
            hist_mc_monthly = hist_price.resample('ME').mean()
            avg_price_2y = hist_mc_monthly["Close"].mean()
        else:
            current_price = np.nan
            high_52w = np.nan
            ma_200 = np.nan
            avg_price_2y = np.nan

        shares = fast.get("shares", np.nan)

        # Spot Market Cap
        if pd.notna(fast.get("market_cap")):
            spot_mcap = fast.get("market_cap")
        elif pd.notna(current_price) and pd.notna(shares):
            spot_mcap = current_price * shares
        else:
            spot_mcap = np.nan

        # Avg market cap (24-Month Rolling)
        avg_mcap = avg_price_2y * shares if pd.notna(avg_price_2y) and pd.notna(shares) else np.nan

        # 🕋 CORRECTED SHARIAH RATIOS (Fixed Denominators)
        debt_assets = safe_ratio(debt, assets)  # For AAOIFI Rule
        debt_avg = safe_ratio(debt, avg_mcap)   # For MSCI Rule (Market Cap Avg)
        debt_spot = safe_ratio(debt, spot_mcap) # For Dow Jones Rule (Spot/Current Cap)
        impure = safe_ratio(interest, revenue)

        def check(val, limit):
            return True if pd.notna(val) and val < limit else False if pd.notna(val) else None

        # Framework Evaluators
        aaoifi_ok = check(debt_assets, 30) and check(impure, 5) # Debt to Assets < 30%
        msci_ok = check(debt_avg, 33) and check(impure, 5)     # Debt to 36m Avg Cap < 33%
        dj_ok = check(debt_spot, 33) and check(impure, 5)      # Debt to Spot Market Cap < 33%

        def disp(ok, val):
            if ok is None:
                return "⚠️ Data unavailable"
            return f"{'✅' if ok else '❌'} ({val:.1f}%)"

        # Consensus tracking across all 3 rulesets
        checks = [aaoifi_ok, msci_ok, dj_ok]
        if any(v is False for v in checks if v is not None):
            consensus = "❌ NON‑COMPLIANT"
        elif all(v is True for v in checks if v is not None):
            consensus = "✅ UNIVERSALLY COMPLIANT"
        else:
            consensus = "⚠️ INCONCLUSIVE"

        # ---- Calculations ----
        upside_52w = (
            (high_52w - current_price) / current_price * 100
            if pd.notna(current_price) and current_price > 0
            else np.nan
        )

        above_200dma = current_price > ma_200 if pd.notna(ma_200) and pd.notna(current_price) else False

        peg = fast.get("peg_ratio", np.nan)
        roe = fast.get("return_on_equity", np.nan)

        buy_score = sum([
            above_200dma,
            pd.notna(upside_52w) and upside_52w > 15,
            pd.notna(peg) and peg < 1.5,
            pd.notna(roe) and roe > 0.10
        ])

        # ✅ Minimum pause time (100ms) to bypass Yahoo constraints while maxing speed
        time.sleep(0.1)

        return {
            "Ticker": ticker,
            "Company Name": company_name,
            "AAOIFI (Asset)": disp(aaoifi_ok, debt_assets),
            "MSCI (Avg Cap)": disp(msci_ok, debt_avg),
            "Dow Jones (Spot Cap)": disp(dj_ok, debt_spot),
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
            "AAOIFI (Asset)": "❌",
            "MSCI (Avg Cap)": "❌",
            "Dow Jones (Spot Cap)": "❌",
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
