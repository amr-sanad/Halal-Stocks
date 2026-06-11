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
    "Data sourced live from Yahoo Finance via yfinance."
)

# --------------------------------------------------
# LOAD PORTFOLIO
# --------------------------------------------------
portfolio_df = pd.read_csv("portfolio.csv")
tickers = portfolio_df["Ticker"].dropna().str.upper().tolist()

# --------------------------------------------------
# ADR / GLOBAL MAP
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
# REPAIRED & STABLE FINANCIAL HELPERS
# --------------------------------------------------
def first_existing(df, labels, info_dict=None, info_keys=None):
    """
    Robust financial extractor using the correct .iloc[0] syntax 
    to prevent calculation engine logic crashes.
    """
    if df is not None and not df.empty:
        try:
            # Flatten multi-tiered yfinance index layouts if they exist
            if isinstance(df.index, pd.MultiIndex):
                clean_index = [str(x).lower().strip() for x in df.index.get_level_values(0)]
            else:
                clean_index = [str(x).lower().strip() for x in df.index]

            index_map = dict(zip(clean_index, df.index))

            for lbl in labels:
                lbl_clean = str(lbl).lower().strip()
                if lbl_clean in index_map:
                    row_data = df.loc[index_map[lbl_clean]]
                    
                    # ✅ FIXED REGRESSION: Restored the exact working numerical item selection syntax [.iloc[0]]
                    if isinstance(row_data, (pd.Series, pd.DataFrame)):
                        return float(row_data.iloc[0])
                    return float(row_data)
        except:
            pass

    # Secondary text layout fallback search (Vital recovery step for XOM, KPTSF, and Cairo markets)
    if info_dict and info_keys:
        for k in info_keys:
            if k in info_dict and info_dict[k] is not None:
                try:
                    return float(info_dict[k])
                except:
                    continue
    return np.nan

def safe_ratio(num, den):
    if pd.isna(num) or pd.isna(den) or den <= 0:
        return np.nan
    return (num / den) * 100

# --------------------------------------------------
# ANALYSIS ENGINE
# --------------------------------------------------
def analyze_ticker(ticker):
    try:
        fundamental_ticker = ADR_MAP.get(ticker, ticker)
        stock = yf.Ticker(fundamental_ticker)
        price_stock = yf.Ticker(ticker)

        # ---- SECURE INFO DICTIONARIES ----
        info = {}
        try:
            info = stock.info
        except:
            pass

        try:
            fast = stock.fast_info
        except:
            fast = {}

        company_name = info.get("longName", ticker) if info else ticker

        # ---- LIVE STATEMENT EXTRACTION ----
        bs = None
        is_stmt = None
        try:
            bs = stock.balance_sheet
            is_stmt = stock.financials
        except:
            pass

        # Parse metrics using multi-index tracking and direct data fallbacks simultaneously
        assets = first_existing(bs, ["Total Assets", "TotalAssets"], info, ["totalAssets"])
        
        debt = first_existing(bs, [
            "Total Debt", "Long Term Debt", "LongTermDebt", 
            "Total Liabilities", "Total Liab", "Current Liabilities"
        ], info, ["totalDebt", "totalLiabilities"])
        
        revenue = first_existing(is_stmt, ["Total Revenue", "Revenue", "TotalRevenue"], info, ["totalRevenue"])
        
        interest = first_existing(is_stmt, [
            "Interest Income", "InterestIncome", 
            "Interest and Investment Income", "Net Interest Income"
        ], info, ["interestIncome"])

        if pd.notna(revenue) and pd.isna(interest):
            interest = 0.0

        # ---- UNIFORM TIME PROFILE HISTORICAL PRICES ----
        hist_price = price_stock.history(period="3y")
        
        if not hist_price.empty:
            current_price = hist_price["Close"].iloc[-1]
            high_52w = hist_price["Close"].max()
            ma_200 = hist_price["Close"].rolling(200).mean().iloc[-1] if len(hist_price) >= 200 else np.nan
            
            # Form accurate historical rolling capitalization timelines
            monthly_data = hist_price.resample('ME').mean()
            avg_price_36m = monthly_data["Close"].tail(36).mean()  # MSCI Delineator
            avg_price_24m = monthly_data["Close"].tail(24).mean()  # Dow Jones Delineator
        else:
            # Regional Exchange Fallbacks
            current_price = info.get("previousClose", np.nan) if info else np.nan
            high_52w = info.get("fiftyTwoWeekHigh", np.nan) if info else np.nan
            ma_200 = info.get("twoHundredDayAverage", np.nan) if info else np.nan
            avg_price_36m = current_price
            avg_price_24m = current_price

        # Recover historical outstanding shares securely across all regional markets
        shares = fast.get("shares", np.nan)
        if pd.isna(shares) and info:
            shares = info.get("sharesOutstanding", np.nan)

        # Multi-Methodology Market Cap Calculations
        mcap_36m_avg = avg_price_36m * shares if pd.notna(avg_price_36m) and pd.notna(shares) else np.nan
        mcap_24m_avg = avg_price_24m * shares if pd.notna(avg_price_24m) and pd.notna(shares) else np.nan

        # 🕋 EXECUTING METHODOLOGY SPECIFIC FORMULAS
        debt_assets = safe_ratio(debt, assets)      # AAOIFI Screen
        debt_msci = safe_ratio(debt, mcap_36m_avg)  # MSCI Screen
        debt_dj = safe_ratio(debt, mcap_24m_avg)    # Dow Jones Screen
        impure = safe_ratio(interest, revenue)

        def check(val, limit):
            if pd.isna(val): 
                return None
            return val < limit

        aaoifi_ok = check(debt_assets, 30) and check(impure, 5)
        msci_ok = check(debt_msci, 33) and check(impure, 5)
        dj_ok = check(debt_dj, 33) and check(impure, 5)

        def disp(ok, val):
            if ok is None:
                return "⚠️ Data incomplete"
            return f"{'✅' if ok else '❌'} ({val:.1f}%)"

        # ---- STRICT CONSENSUS VALIDATOR LOGIC ----
        checks = [aaoifi_ok, msci_ok, dj_ok]
        
        if any(v is False for v in checks if v is not None):
            consensus = "❌ NON‑COMPLIANT"
        elif all(v is True for v in checks):
            consensus = "✅ UNIVERSALLY COMPLIANT"
        elif any(v is True for v in checks) and any(v is None for v in checks):
            consensus = "⚠️ PARTIALLY COMPLIANT (Data missing in some screens)"
        else:
            consensus = "⚠️ INCONCLUSIVE"

        # ---- VALUATION AND BUY SIGNALS ----
        upside_52w = (
            (high_52w - current_price) / current_price * 100
            if pd.notna(current_price) and pd.notna(high_52w) and current_price > 0
            else np.nan
        )

        above_200dma = current_price > ma_200 if pd.notna(ma_200) and pd.notna(current_price) else False
        peg = info.get("pegRatio", np.nan) if info else np.nan
        roe = info.get("returnOnEquity", np.nan) if info else np.nan

        buy_score = sum([
            above_200dma,
            pd.notna(upside_52w) and upside_52w > 15,
            pd.notna(peg) and peg < 1.5,
            pd.notna(roe) and roe > 0.10
        ])

        time.sleep(0.1)

        return {
            "Ticker": ticker,
            "Company Name": company_name,
            "AAOIFI (Asset)": disp(aaoifi_ok, debt_assets),
            "MSCI (36m Avg Cap)": disp(msci_ok, debt_msci),
            "Dow Jones (24m Avg Cap)": disp(dj_ok, debt_dj),
            "Impure Revenue %": None if pd.isna(impure) else round(impure, 1),
            "Consensus": consensus,
            "Current Price": round(current_price, 2) if pd.notna(current_price) else None,
            "Upside to 52W High %": None if pd.isna(upside_52w) else round(upside_52w, 1),
            "Above 200DMA": "✅" if above_200dma else "❌",
            "Buy Score (0–4)": int(buy_score),
            "Currency": info.get("currency", "Unknown") if info else "Unknown",
        }

    except Exception as e:
        return {
            "Ticker": ticker,
            "Company Name": "CRITICAL ENGINE ERROR",
            "AAOIFI (Asset)": "⚠️ Data missing",
            "MSCI (36m Avg Cap)": "⚠️ Data missing",
            "Dow Jones (24m Avg Cap)": "⚠️ Data missing",
            "Impure Revenue %": None,
            "Consensus": "❌ ERROR",
            "Current Price": None,
            "Upside to 52W High %": None,
            "Above 200DMA": "❌",
            "Buy Score (0–4)": 0,
            "Currency": "Error",
        }

# --------------------------------------------------
# EXECUTION LOOP RUNNER
# --------------------------------------------------
if st.button("Run Full Analysis"):
    results = []

    for t in tickers:
        st.write(f"Scraping live tracking metrics for: {t}...")
        results.append(analyze_ticker(t))

    df = pd.DataFrame(results)
    st.dataframe(df, use_container_width=True)
    df.to_csv("latest_results.csv", index=False)
    st.success("✅ Live tracking loop complete.")
    
