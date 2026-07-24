"""
Portfolio Ledger — Streamlit
Track positions, daily/total % moves, and a target-price scenario.

Run locally:   streamlit run portfolio_tracker_app.py
Deploy:        push to a repo + deploy on Streamlit Community Cloud,
                same as your LP app. Positions are saved to portfolio_data.csv
                next to this file, so on Streamlit Cloud they'll persist
                between sessions but reset on redeploy unless you wire up
                a real DB/gist — fine for personal use, flag it if you want
                that upgraded.
"""

import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

# ---------------------------------------------------------------- config

st.set_page_config(page_title="Portfolio Ledger", page_icon="📒", layout="wide")

DATA_FILE = os.path.join(os.path.dirname(__file__), "portfolio_data.csv")

AMBER = "#F5A623"
GREEN = "#3ECF8E"
RED = "#FF5C6C"
INK = "#0A0D12"
PANEL = "#12161F"
MUTED = "#767F8F"

COLUMNS = ["ticker", "shares", "buy_price", "current_price", "prev_close", "target_price"]

# ---------------------------------------------------------------- style

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {INK}; }}
    [data-testid="stMetric"] {{
        background: {PANEL};
        border: 1px solid #232A38;
        border-radius: 10px;
        padding: 12px 14px;
    }}
    [data-testid="stMetricLabel"] {{ color: {MUTED}; }}
    h1, h2, h3 {{ font-family: 'IBM Plex Sans', sans-serif; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- data i/o

def load_data() -> pd.DataFrame:
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = np.nan
        return df[COLUMNS]
    return pd.DataFrame(
        [
            {"ticker": "AAPL", "shares": 10, "buy_price": 150.00, "current_price": 172.30,
             "prev_close": 170.10, "target_price": 220.00},
        ],
        columns=COLUMNS,
    )


def save_data(df: pd.DataFrame):
    df.to_csv(DATA_FILE, index=False)


if "portfolio" not in st.session_state:
    st.session_state.portfolio = load_data()

# ---------------------------------------------------------------- header

st.markdown(
    f"<div style='color:{AMBER}; font-family:monospace; font-size:12px; "
    f"letter-spacing:2px;'>LAUGHING PROMETHEUS · POSITIONS</div>",
    unsafe_allow_html=True,
)
st.title("Portfolio Ledger")

st.caption(
    "Edit prices directly in the table below. Add rows with the ➕ at the bottom, "
    "delete with the row checkbox + trash icon. Target price is optional."
)

# ---------------------------------------------------------------- editable table

edited = st.data_editor(
    st.session_state.portfolio,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "ticker": st.column_config.TextColumn("Ticker", width="small"),
        "shares": st.column_config.NumberColumn("Shares", min_value=0.0, step=1.0, format="%.4f"),
        "buy_price": st.column_config.NumberColumn("Buy price", min_value=0.0, format="$%.2f"),
        "current_price": st.column_config.NumberColumn("Current price", min_value=0.0, format="$%.2f"),
        "prev_close": st.column_config.NumberColumn("Prev close", min_value=0.0, format="$%.2f",
                                                      help="Used to compute today's % move"),
        "target_price": st.column_config.NumberColumn("Target price", format="$%.2f",
                                                        help="Optional — leave blank to skip"),
    },
    key="editor",
)

# normalize + persist
edited = edited.dropna(subset=["ticker"]).copy()
edited["ticker"] = edited["ticker"].str.upper().str.strip()
edited["prev_close"] = edited["prev_close"].fillna(edited["current_price"])

if not edited.equals(st.session_state.portfolio):
    st.session_state.portfolio = edited
    save_data(edited)

df = edited.copy()

if df.empty:
    st.info("Add a position above to get started.")
    st.stop()

# ---------------------------------------------------------------- derived metrics

df["value"] = df["shares"] * df["current_price"]
df["cost"] = df["shares"] * df["buy_price"]
df["total_gain"] = df["value"] - df["cost"]
df["total_pct"] = np.where(df["cost"] != 0, df["total_gain"] / df["cost"] * 100, 0)
df["daily_gain"] = df["shares"] * (df["current_price"] - df["prev_close"])
df["daily_pct"] = np.where(df["prev_close"] != 0,
                            (df["current_price"] - df["prev_close"]) / df["prev_close"] * 100, 0)

has_target = df["target_price"].notna()
df["target_value"] = np.where(has_target, df["shares"] * df["target_price"], df["value"])
df["target_pct_from_buy"] = np.where(
    has_target & (df["buy_price"] != 0),
    (df["target_price"] - df["buy_price"]) / df["buy_price"] * 100,
    np.nan,
)
df["target_pct_from_current"] = np.where(
    has_target & (df["current_price"] != 0),
    (df["target_price"] - df["current_price"]) / df["current_price"] * 100,
    np.nan,
)

total_value = df["value"].sum()
total_cost = df["cost"].sum()
total_daily_gain = df["daily_gain"].sum()
prev_total_value = total_value - total_daily_gain
total_daily_pct = (total_daily_gain / prev_total_value * 100) if prev_total_value else 0
total_gain = total_value - total_cost
total_pct = (total_gain / total_cost * 100) if total_cost else 0
target_total_value = df["target_value"].sum()
target_gain = target_total_value - total_value
target_pct = (target_gain / total_value * 100) if total_value else 0

# ---------------------------------------------------------------- summary

c1, c2, c3 = st.columns(3)
c1.metric("Portfolio value", f"${total_value:,.2f}", f"cost ${total_cost:,.2f}")
c2.metric("Today", f"${total_daily_gain:,.2f}", f"{total_daily_pct:+.2f}%")
c3.metric("Total return", f"${total_gain:,.2f}", f"{total_pct:+.2f}%")

st.divider()

# ---------------------------------------------------------------- position detail

st.subheader("Positions")

for _, r in df.iterrows():
    cols = st.columns([2, 2, 2, 2])
    daily_color = GREEN if r["daily_pct"] >= 0 else RED
    total_color = GREEN if r["total_pct"] >= 0 else RED
    cols[0].markdown(f"**{r['ticker']}**  \n`{r['shares']:g}sh @ ${r['buy_price']:,.2f}`")
    cols[1].markdown(f"**${r['value']:,.2f}**  \n<span style='color:{MUTED}'>value</span>",
                      unsafe_allow_html=True)
    cols[2].markdown(f"<span style='color:{daily_color}'>{r['daily_pct']:+.2f}% today</span>"
                      f"  \n<span style='color:{total_color}'>{r['total_pct']:+.2f}% total</span>",
                      unsafe_allow_html=True)
    if pd.notna(r["target_price"]):
        cols[3].markdown(
            f"<span style='color:{AMBER}'>target ${r['target_price']:,.2f} → "
            f"${r['target_value']:,.2f} ({r['target_pct_from_current']:+.1f}% to go)</span>",
            unsafe_allow_html=True,
        )
    else:
        cols[3].markdown(f"<span style='color:{MUTED}'>no target set</span>", unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------- target scenario

st.subheader("🎯 Target scenario")

if not has_target.any():
    st.caption("Set a target price on a position above to see this projection.")
else:
    st.markdown(
        f"**If targets hit: ${target_total_value:,.2f} ({target_pct:+.2f}% from today's ${total_value:,.2f})**"
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["ticker"], x=df["value"], name="Today", orientation="h",
        marker_color=MUTED,
    ))
    fig.add_trace(go.Bar(
        y=df["ticker"], x=df["target_value"], name="At target", orientation="h",
        marker_color=[AMBER if t else "rgba(0,0,0,0)" for t in has_target],
    ))
    fig.update_layout(
        barmode="group",
        plot_bgcolor=PANEL,
        paper_bgcolor=PANEL,
        font_color="#E9E7E0",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=40, b=10),
        height=max(220, 60 * len(df)),
        xaxis=dict(gridcolor="#232A38", tickprefix="$"),
        yaxis=dict(gridcolor="#232A38"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Grey = today's value · Amber = value if that position's target price is reached "
        "(other positions held at current price). This sums each stock's target scenario "
        "independently — it's not a simulation of every position moving at once."
    )

st.divider()
st.download_button(
    "Download positions as CSV",
    df[COLUMNS].to_csv(index=False).encode("utf-8"),
    file_name="portfolio_positions.csv",
    mime="text/csv",
)
