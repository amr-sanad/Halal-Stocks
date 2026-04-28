import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# -------------------
# Page setup
# -------------------
st.set_page_config(page_title="Consensus Shariah Screener", layout="wide")

st.title("🕋 Global Shariah Consensus Screener")
st.write("AAOIFI (Spot) vs (24m Avg) with Highlighted Warning Zones.")

# -------------------
# Top disclaimer
# -------------------
st.info(
    "⚠️ This tool is for informational and research purposes only. "
    "It does not constitute financial, investment, or religious advice. "
    "Financial data is sourced from public APIs (e.g., Yahoo Finance) and "
    "may be delayed, incomplete, or inaccurate."
)

ticker_input = st.text_input(
    "Enter Tickers (e.g., TSLA, BY6.GETTEX, VUAG.LSE, ASML.AMS)",
    "TSLA, BY6.GETTEX, VUAG.LSE, ASML.AMS"
)

# -------------------
# Helper functions
# -------------------
def get_stable_mcap(stock):
    hist = stock.history(period="2y", interval="1mo")
    shares = stock.info.get('sharesOutstanding', 0)
    return (hist['Close'].mean() * shares) if not hist.empty and shares > 0 else stock.info.get('marketCap', 0)

def highlight_warnings(row):
    styles = [''] * len(row)

    for i, col in enumerate(row.index):
        # Debt-based columns
        if any(x in col for x in ['AAOIFI', 'DJIM', 'MSCI']):
            try:
                val = float(row[col].split('(')[1].strip('%)'))
                if val > 28:
                    styles[i] = 'background-color: orange; color: black'
            except Exception:
                pass

        # Impure revenue
        if col == 'Impure Rev':
            try:
                val = float(row[col].split('%')[0].replace('⚠️ ', ''))
                if val > 3.5:
                    styles[i] = 'background-color: orange; color: black'
            except Exception:
                pass

    return styles

# -------------------
# Main logic
# -------------------
if st.button("Run Analysis"):
    raw_tickers = [t.strip().upper() for t in ticker_input.split(",")]
    t212_map = {
        ".LSE": ".L",
        ".GETTEX": ".MU",
        ".XETR": ".DE",
        ".AMS": ".AS",
        ".PAR": ".PA",
        ".MIL": ".MI",
    }

    results = []

    for original in raw_tickers:
        symbol = original
        for t212, yf_s in t212_map.items():
            if original.endswith(t212):
                symbol = original.replace(t212, yf_s)
                break

        try:
            with st.spinner(f"Analyzing {original}..."):
                stock = yf.Ticker(symbol)
                info = stock.info
                bs = stock.balance_sheet
                is_stmt = stock.financials

                assets = bs.loc['Total Assets'].iloc[0] if 'Total Assets' in bs.index else 1
                revenue = is_stmt.loc['Total Revenue'].iloc[0] if 'Total Revenue' in is_stmt.index else 1
                debt = bs.loc['Total Debt'].iloc[0] if 'Total Debt' in bs.index else 0

                spot_mcap = info.get('marketCap', 0)
                avg_mc = get_stable_mcap(stock)

                # Interest income
                int_inc_raw = (
                    is_stmt.loc['Interest Income'].iloc[0]
                    if 'Interest Income' in is_stmt.index
                    else np.nan
                )
                has_int_data = pd.notnull(int_inc_raw)
                impure_rev = ((int_inc_raw if has_int_data else 0) / revenue) * 100

                # Ratios
                debt_assets = (debt / assets) * 100
                debt_spot_mc = (debt / spot_mcap) * 100 if spot_mcap > 0 else 0
                debt_avg_mc = (debt / avg_mc) * 100 if avg_mc > 0 else 0

                # Normalization guard
                if debt_avg_mc > 500:
                    debt_avg_mc = debt_assets * 1.1
                if debt_spot_mc > 500:
                    debt_spot_mc = debt_assets * 1.1

                # Compliance checks
                p_spot = (debt_spot_mc < 30) and (impure_rev < 5)
                p_avg = (debt_avg_mc < 30) and (impure_rev < 5)
                p_msci = (debt_assets < 33) and (impure_rev < 5)

                consensus = "✅ COMPLIANT" if (p_avg and p_msci) else "❌ NON-COMPLIANT"
                rev_display = f"{impure_rev:.1f}%" if has_int_data else "⚠️ 0.0% (No Data)"

                results.append({
                    "Ticker": original,
                    "Company Name": info.get('longName', 'Unknown'),
                    "AAOIFI (Spot)": f"{'✅' if p_spot else '❌'} ({debt_spot_mc:.1f}%)",
                    "AAOIFI (24m Avg)": f"{'✅' if p_avg else '❌'} ({debt_avg_mc:.1f}%)",
                    "MSCI (Asset)": f"{'✅' if p_msci else '❌'} ({debt_assets:.1f}%)",
                    "Impure Rev": rev_display,
                    "Consensus": consensus,
                })

        except Exception as e:
            st.error(f"Error on {original}: {e}")

    if results:
        df = pd.DataFrame(results)
        styled_df = df.style.apply(highlight_warnings, axis=1)
        st.table(styled_df)

# -------------------
# Footer disclaimer
# -------------------
st.markdown("<hr>", unsafe_allow_html=True)
st.markdown(
    "<small>"
    "Informational use only · Not financial or investment advice · "
    "Data from public sources (Yahoo Finance)"
    "</small>",
    unsafe_allow_html=True
)
