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
PORTFOLIO_FILE = "portfolio.xlsx"
portfolio_df = pd.read_excel(PORTFOLIO_FILE)
tickers = portfolio_df["Ticker"].dropna().str.upper().tolist()

# --------------------------------------------------
# ADR FALLBACK MAP (Option B)
# --------------------------------------------------
ADR_MAP = {
    "ASML.AS": "ASML",
    "SAP.DE": "SAP",
    "SIE.DE": "SIEGY",
    "BAYN.DE": "BAYRY",
    "OR.PA": "OR.PA",   # no ADR, kept as-is
    "AI.PA": "AI.PA",   # no ADR, kept as-is
}

# --------------------------------------------------
# HELPER FUNCTIONS (Option A)
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
# ANALYSIS FUNCTION
# --------------------------------------------------
def analyze_ticker(ticker):
    def extract_core(stock_obj):
        info = stock_obj.info
        bs = stock_obj.balance_sheet
        is_stmt = stock_obj.financials

        assets = first_existing(bs, ["Total Assets"])
        debt = first_existing(bs, ["Total Debt", "Long Term Debt", "Total Liab"])
        revenue = first_existing(is_stmt, ["Total Revenue", "Revenue"])

        # Interest income is OPTIONAL (Tesla-style companies)
        interest = first_existing(
            is_stmt,
            ["Interest Income", "Interest and Investment Income"]
        )

        # If revenue exists but interest is missing → assume 0
        if pd.notna(revenue) and pd.isna(interest):
            interest = 0.0

        return info, assets, debt, revenue, interest, stock_obj

    # ---- First try: given ticker ----
    stock = yf.Ticker(ticker)
    info, assets, debt, revenue, interest, used_stock = extract_core(stock)

    used_adr = False

    # ---- ADR fallback if CORE fields missing ----
    if pd.isna(assets) or pd.isna(revenue):
        adr = ADR_MAP.get(ticker)
        if adr and adr != ticker:
            stock_adr = yf.Ticker(adr)
            info_adr, assets_adr, debt_adr, revenue_adr, interest_adr, _ = extract_core(stock_adr)

            if pd.notna(assets_adr) and pd.notna(revenue_adr):
                assets, debt, revenue, interest = (
                    assets_adr, debt_adr, revenue_adr, interest_adr
                )
                used_adr = True

    # ---- Market caps ----
    spot_mcap = info.get("marketCap", np.nan)
    hist_mc = stock.history(period="2y", interval="1mo")
    shares = info.get("sharesOutstanding", np.nan)
    avg_mcap = (
        hist_mc["Close"].mean() * shares
        if not hist_mc.empty and pd.notna(shares)
        else np.nan
    )

    # ---- Ratios ----
    debt_assets = safe_ratio(debt, assets)
    debt_spot_mc = safe_ratio(debt, spot_mcap)
    debt_avg_mc = safe_ratio(debt, avg_mcap)
    impure_rev = safe_ratio(interest, revenue)

    def check(val, limit):
        return None if pd.isna(val) else val < limit

    spot_ok = check(debt_spot_mc, 30) and check(impure_rev, 5)
    avg_ok = check(debt_avg_mc, 30) and check(impure_rev, 5)
    msci_ok = check(debt_assets, 33) and check(impure_rev, 5)

    def disp(ok, val):
        if ok is None:
            return "⚠️ Data unavailable"
        return f"{'✅' if ok else '❌'} ({val:.1f}%)"

    # ---- Consensus ----
    evaluations = [spot_ok, avg_ok, msci_ok]
    if any(v is False for v in evaluations):
        consensus = "❌ NON‑COMPLIANT"
    elif any(v is True for v in evaluations):
        consensus = "✅ COMPLIANT"
    else:
        consensus = "⚠️ INCONCLUSIVE"

    return {
        "Ticker": ticker,
        "Company Name": info.get("longName", "Unknown"),
        "AAOIFI (Spot)": disp(spot_ok, debt_spot_mc),
        "AAOIFI (24m Avg)": disp(avg_ok, debt_avg_mc),
        "MSCI (Asset)": disp(msci_ok, debt_assets),
        "Impure Revenue %": None if pd.isna(impure_rev) else round(impure_rev, 1),
        "Consensus": consensus,
        "ADR Used for Ratios": "Yes" if used_adr else "No",
        "Current Price": round(info.get("currentPrice", np.nan), 2),
    }

    # ---------- Decision indicators ----------
    current_price = info.get("currentPrice", np.nan)
    high_52w = info.get("fiftyTwoWeekHigh", np.nan)
    low_52w = info.get("fiftyTwoWeekLow", np.nan)

    upside_52w = (
        (high_52w - current_price) / current_price * 100
        if pd.notna(current_price) and pd.notna(high_52w)
        else np.nan
    )

    hist = stock.history(period="1y")
    ma_200 = hist["Close"].rolling(200).mean().iloc[-1] if len(hist) >= 200 else np.nan
    above_200dma = current_price > ma_200 if pd.notna(ma_200) else False

    range_pos = (
        (current_price - low_52w) / (high_52w - low_52w) * 100
        if pd.notna(high_52w) and pd.notna(low_52w) and high_52w != low_52w
        else np.nan
    )

    forward_pe = info.get("forwardPE", np.nan)
    peg = info.get("pegRatio", np.nan)
    roe = info.get("returnOnEquity", np.nan)
    roe_pct = roe * 100 if pd.notna(roe) else np.nan

    buy_score = 0
    buy_score += 1 if above_200dma else 0
    buy_score += 1 if upside_52w and upside_52w > 15 else 0
    buy_score += 1 if peg and peg < 1.5 else 0
    buy_score += 1 if roe_pct and roe_pct > 10 else 0

    return {
        "Ticker": ticker,
        "Company Name": info.get("longName", "Unknown"),
        "AAOIFI (Spot)": aaoifi_spot,
        "AAOIFI (24m Avg)": aaoifi_avg,
        "MSCI (Asset)": msci_disp,
        "Impure Revenue %": None if pd.isna(impure_rev) else round(impure_rev, 1),
        "Consensus": consensus,
        "Current Price": round(current_price, 2),
        "Upside to 52W High %": None if pd.isna(upside_52w) else round(upside_52w, 1),
        "Above 200DMA": "✅" if above_200dma else "❌",
        "52W Range Position %": None if pd.isna(range_pos) else round(range_pos, 1),
        "Forward P/E": None if pd.isna(forward_pe) else round(forward_pe, 1),
        "PEG": None if pd.isna(peg) else round(peg, 2),
        "ROE %": None if pd.isna(roe_pct) else round(roe_pct, 1),
        "Buy Score (0–4)": buy_score,
        "ADR Used for Ratios": "Yes" if used_adr else "No",
    }

# --------------------------------------------------
# RUN ANALYSIS
# --------------------------------------------------
if st.button("Run Full Analysis"):
    results = []
    for t in tickers:
        with st.spinner(f"Analyzing {t}…"):
            results.append(analyze_ticker(t))

    df = pd.DataFrame(results)
    st.dataframe(df, use_container_width=True)

    df.to_excel("latest_results.xlsx", index=False)
    st.success("✅ Analysis completed — saved to latest_results.xlsx")

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
