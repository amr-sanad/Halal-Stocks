import time
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import finnhub

# --------------------------------------------------
# CONFIG & AUTH
# --------------------------------------------------
st.set_page_config(page_title="Consensus Shariah Screener", layout="wide")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.text_input("Password", type="password", key="pw")
        if st.session_state.pw == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        st.stop()

check_password()

# --------------------------------------------------
# TITLE & DISCLAIMER
# --------------------------------------------------
st.title("🕋 Global Shariah Consensus Screener")

st.info(
    "⚠️ Informational and research use only. Not financial or investment advice. "
    "Data sourced from Yahoo Finance and Finnhub. Results may be incomplete or inaccurate."
)

# --------------------------------------------------
# INIT FINNHUB CLIENT
# --------------------------------------------------
finnhub_client = finnhub.Client(api_key=st.secrets["FINNHUB_API_KEY"])

# --------------------------------------------------
# COMPANY SEARCH
# --------------------------------------------------
st.subheader("🔎 Company → Ticker Search")
company_query = st.text_input("Enter company name")
if company_query:
    r = finnhub_client.symbol_lookup(company_query)
    if r.get("result"):
        st.write("Matching tickers:")
        for item in r["result"][:5]:
            st.write(f"**{item['symbol']}** — {item['description']}")

# --------------------------------------------------
# LOAD PORTFOLIO
# --------------------------------------------------
PORTFOLIO_FILE = "portfolio.xlsx"
portfolio_df = pd.read_excel(PORTFOLIO_FILE)
tickers = portfolio_df["Ticker"].dropna().unique().tolist()

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------
def get_shariah_metrics(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    bs = stock.balance_sheet
    is_stmt = stock.financials

    assets = bs.loc['Total Assets'].iloc[0] if 'Total Assets' in bs.index else 1
    debt = bs.loc['Total Debt'].iloc[0] if 'Total Debt' in bs.index else 0
    revenue = is_stmt.loc['Total Revenue'].iloc[0] if 'Total Revenue' in is_stmt.index else 1

    int_inc = is_stmt.loc['Interest Income'].iloc[0] if 'Interest Income' in is_stmt.index else 0
    impure_rev = (int_inc / revenue) * 100 if revenue else 0
    debt_assets = (debt / assets) * 100

    compliant = debt_assets < 33 and impure_rev < 5

    return debt_assets, impure_rev, compliant

def get_analyst_data(ticker):
    rec = finnhub_client.recommendation_trends(ticker)
    price = finnhub_client.price_target(ticker)
    quote = finnhub_client.quote(ticker)

    if not rec:
        return None

    r = rec[0]
    buys = r.get("buy", 0) + r.get("strongBuy", 0)
    total = sum(r.get(k, 0) for k in ["buy", "hold", "sell", "strongBuy", "strongSell"])
    buy_pct = (buys / total) * 100 if total else 0

    current = quote.get("c", np.nan)
    target = price.get("targetMean", np.nan)
    upside = ((target - current) / current) * 100 if current and target else np.nan

    return buy_pct, target, current, upside, total

# --------------------------------------------------
# RUN ANALYSIS
# --------------------------------------------------
if st.button("Run Portfolio Analysis"):
    results = []

    for ticker in tickers:
        with st.spinner(f"Analyzing {ticker}..."):
            try:
                debt_assets, impure_rev, halal = get_shariah_metrics(ticker)
                analyst = get_analyst_data(ticker)

                time.sleep(1)  # ✅ FINNHUB RATE‑LIMIT CONTROL

                if analyst:
                    buy_pct, target, price, upside, analysts = analyst
                else:
                    buy_pct = target = price = upside = analysts = np.nan

                results.append({
                    "Ticker": ticker,
                    "Debt / Assets %": round(debt_assets, 1),
                    "Impure Revenue %": round(impure_rev, 1),
                    "Shariah Status": "✅ COMPLIANT" if halal else "❌ NON‑COMPLIANT",
                    "Buy %": round(buy_pct, 1),
                    "Target Price": round(target, 2) if target else None,
                    "Current Price": round(price, 2) if price else None,
                    "Upside %": round(upside, 1) if upside else None,
                    "Analyst Count": analysts,
                })

            except Exception as e:
                st.error(f"{ticker}: {e}")

    df = pd.DataFrame(results)
    st.dataframe(df)

    # Save results
    df.to_excel("latest_results.xlsx", index=False)
    st.success("✅ Analysis complete — results saved to latest_results.xlsx")

# --------------------------------------------------
# FOOTER ATTRIBUTION
# --------------------------------------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<small>"
    "Data sources: Yahoo Finance (yfinance) and Finnhub.io. "
    "Finnhub data © Finnhub. Informational use only."
    "</small>",
    unsafe_allow_html=True
)
