from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh


API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
REFRESH_MS = int(os.getenv("UI_REFRESH_MS", "1500"))


def _get_json(path: str):
    url = f"{API_BASE}{path}"
    response = requests.get(url, timeout=3)
    response.raise_for_status()
    return response.json()


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}Rs {abs(value):,.2f}"


def render() -> None:
    st.set_page_config(page_title="Live PnL Dashboard", layout="wide")
    st.title("Live Multi-Trader PnL")

    st_autorefresh(interval=REFRESH_MS, key="live-refresh")

    try:
        pnl = _get_json("/pnl")
        positions = _get_json("/positions")
    except Exception as exc:
        st.error(f"Backend not reachable: {exc}")
        st.stop()

    combined = pnl["combined"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Combined Total P&L", _money(combined["total_pnl"]))
    c2.metric("Combined Current P&L", _money(combined["current_pnl"]))
    c3.metric("Combined Realized P&L", _money(combined["realized_pnl"]))
    c4.metric("Combined Day Realized P&L", _money(combined["day_realized_pnl"]))

    st.subheader("Trader-wise")
    cols = st.columns(max(1, len(pnl["traders"])))
    for idx, trader in enumerate(pnl["traders"]):
        with cols[idx]:
            st.markdown(f"### {trader['name']}")
            st.write(f"Current: {_money(trader['current_pnl'])}")
            st.write(f"Realized: {_money(trader['realized_pnl'])}")
            st.write(f"Day Realized: {_money(trader['day_realized_pnl'])}")
            st.write(f"Total: {_money(trader['total_pnl'])}")

    st.subheader("Open Positions")
    if positions:
        df = pd.DataFrame(positions)
        df = df[
            [
                "trader_name",
                "symbol",
                "quantity",
                "avg_price",
                "ltp",
                "side",
                "current_pnl",
            ]
        ]
        df.columns = ["Trader", "Symbol", "Qty", "Avg Price", "LTP", "Side", "Current P&L"]
        st.dataframe(df, width="stretch")
    else:
        st.info("No open positions")


if __name__ == "__main__":
    render()
