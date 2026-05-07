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


def _color(value: float) -> str:
    if value > 0:
        return "#16c784"
    if value < 0:
        return "#ff5b6e"
    return "#9aa4b2"


def _card(title: str, current: float, total: float) -> str:
    c_col = _color(current)
    t_col = _color(total)
    return f"""
    <div class=\"pnl-card\">
      <div class=\"pnl-title\">{title}</div>
      <div class=\"pnl-row\"><span>Current</span><strong style=\"color:{c_col}\">{_money(current)}</strong></div>
      <div class=\"pnl-row\"><span>Total</span><strong style=\"color:{t_col}\">{_money(total)}</strong></div>
    </div>
    """


def render() -> None:
    st.set_page_config(page_title="PnL Corner", layout="centered")

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {display: none;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        .block-container {
          max-width: 360px;
          padding-top: 0.25rem;
          padding-bottom: 0.35rem;
          padding-left: 0.35rem;
          padding-right: 0.35rem;
        }

        .pnl-card {
          border: 1px solid rgba(154,164,178,0.25);
          border-radius: 10px;
          padding: 0.45rem 0.55rem;
          margin-bottom: 0.35rem;
          background: rgba(8, 12, 22, 0.92);
        }

        .pnl-title {
          font-size: 0.87rem;
          font-weight: 700;
          margin-bottom: 0.20rem;
          color: #e7edf7;
        }

        .pnl-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.80rem;
          margin-top: 0.05rem;
          color: #b7c2d0;
        }

        .pnl-row strong {
          font-size: 0.90rem;
          font-weight: 700;
        }

        .tiny-muted {
          color: #9aa4b2;
          font-size: 0.70rem;
          margin-top: 0.2rem;
          text-align: right;
        }
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

    st.markdown(
        _card(
            "Combined",
            float(combined.get("current_pnl", 0.0)),
            float(combined.get("total_pnl", 0.0)),
        ),
        unsafe_allow_html=True,
    )

    for trader in pnl.get("traders", []):
        st.markdown(
            _card(
                str(trader.get("name", "Trader")),
                float(trader.get("current_pnl", 0.0)),
                float(trader.get("total_pnl", 0.0)),
            ),
            unsafe_allow_html=True,
        )

    st.markdown('<div class="tiny-muted">Refresh: {} ms</div>'.format(REFRESH_MS), unsafe_allow_html=True)


if __name__ == "__main__":
    render()
