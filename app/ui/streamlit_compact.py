from __future__ import annotations

import os

import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh


API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
REFRESH_MS = int(os.getenv("UI_REFRESH_MS", "1000"))


def _get_json(path: str):
    url = f"{API_BASE}{path}"
    response = requests.get(url, timeout=3)
    response.raise_for_status()
    return response.json()


def _money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}Rs {abs(value):,.2f}"


def render() -> None:
    st.set_page_config(page_title="PnL Mini", layout="centered")

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {display: none;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {padding-top: 0.6rem; padding-bottom: 0.6rem; max-width: 420px;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st_autorefresh(interval=REFRESH_MS, key="mini-live-refresh")

    try:
        pnl = _get_json("/pnl")
    except Exception as exc:
        st.error(f"API error: {exc}")
        st.stop()

    combined = pnl["combined"]

    st.markdown("### Live PnL")
    st.metric("Total", _money(combined["total_pnl"]))
    c1, c2 = st.columns(2)
    c1.metric("Current", _money(combined["current_pnl"]))
    c2.metric("Day Realized", _money(combined["day_realized_pnl"]))

    for trader in pnl["traders"]:
        st.caption(
            f"{trader['name']}: Total {_money(trader['total_pnl'])} | "
            f"Current {_money(trader['current_pnl'])}"
        )


if __name__ == "__main__":
    render()
