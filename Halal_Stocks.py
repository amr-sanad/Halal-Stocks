import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

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
portfolio_df = pd.read_excel("portfolio.xlsx")
tickers = portfolio_df["Ticker"].dropna().str.upper().tolist()

# --------------------------------------------------
# ADR MAP
# --------------------------------------------------
ADR_MAP = {
    "IFX.DE": "IFNNY",
    "ASML.AS": "ASML",
    "SAP.DE": "SAP",
    "SIE.DE": "SIEGY",
    "BAYN.DE": "BAYRY",
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

    def extract(stock):
        info = stock.info
        bs = stock.balance_sheet
        is_stmt = stock.financials

        assets = first_existing(bs, ["Total Assets"])
        debt = first_existing(bs, ["Total Debt", "Long Term Debt", "Total Liab"])
        revenue = first_existing(is_stmt, ["Total Revenue", "Revenue"])
        interest = first_existing(is_stmt, ["Interest Income", "Interest and Investment Income"])

        if pd.notna(revenue) and pd.isna(interest):
            interest = 0.0  # Tesla-style

        return info, assets, debt, revenue, interest

    # Try primary ticker
    stock = yf.Ticker(ticker)
    info, assets, debt, revenue, interest = extract(stock)
    used_adr = False

    # ADR fallback if core fields missing
    if pd.isna(assets) or pd.isna(revenue):
        adr = ADR_MAP.get(ticker)
        if adr:
            adr_stock = yf.Ticker(adr)
            info_adr, assets_adr, debt_adr, revenue_adr, interest_adr = extract(adr_stock)
            if pd.notna(assets_adr) and pd.notna(revenue_adr):
                assets, debt, revenue, interest = assets_adr, debt_adr, revenue_adr, interest_adr
                used_adr = True

    # Market caps
    spot_mcap = info.get("marketCap", np.nan)
    hist = stock.history(period="2y", interval="1mo")
    shares = info.get("sharesOutstanding", np.nan)
    avg_mcap = hist["Close"].mean() * shares if not hist.empty and pd.notna(shares) else np.nan

    # Ratios
    debt_assets = safe_ratio(debt, assets)
    debt_spot = safe_ratio(debt, spot_mcap)
    debt_avg = safe_ratio(debt, avg_mcap)
    impure = safe_ratio(interest, revenue)

    def check(val, limit):
        return None if pd.isna(val) else val < limit

    spot_ok = check(debt_spot, 30) and check(impure, 5)
    avg_ok = check(debt_avg, 30) and check(impure, 5)
    msci_ok = check(debt_assets, 33) and check(impure, 5)

    def disp(ok, val):
        if ok is None:
            return "⚠️ Data unavailable"
        return f"{'✅' if ok else '❌'} ({val:.1f}%)"

    if any(v is False for v in [spot_ok, avg_ok, msci_ok]):
        consensus = "❌ NON‑COMPLIANT"
    elif any(v is True for v in [spot_ok, avg_ok, msci_ok]):
        consensus = "✅ COMPLIANT"
    else:
        consensus = "⚠️ INCONCLUSIVE"

    return {
        "Ticker": ticker,
        "Company Name": info.get("longName", "Unknown"),
        "AAOIFI (Spot)": disp(spot_ok, debt_spot),
        "AAOIFI (24m Avg)": disp(avg_ok, debt_avg),
        "MSCI (Asset)": disp(msci_ok, debt_assets),
        "Impure Revenue %": None if pd.isna(impure) else round(impure, 1),
        "Consensus": consensus,
        "ADR Used for Ratios": "Yes" if used_adr else "No",
        "Current Price": round(info.get("currentPrice", np.nan), 2),
    }

# --------------------------------------------------
# RUN
# --------------------------------------------------
if st.button("Run Full Analysis"):
    df = pd.DataFrame([analyze_ticker(t) for t in tickers])
    st.dataframe(df, use_container_width=True)
    df.to_excel("latest_results.xlsx", index=False)
    st.success("✅ Analysis completed")

# --------------------------------------------------
# FOOTER
# --------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<small>"
    "Shariah ratios derived from public financial statements. "
    "ADR financials may be used where local data is unavailable. "
    "Market data © Yahoo Finance via yfinance. "
    "For personal and educational use only."
    "</small>",
    unsafe_allow_html=True
)
``
