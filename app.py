from pathlib import Path
import re
import sqlite3
import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

st.set_page_config(page_title="2FEXC V2", page_icon="₿", layout="wide")

THEME = {
    "bg": "#05070d",
    "panel": "#0b1220",
    "panel2": "#101827",
    "grid": "#223046",
    "text": "#e5e7eb",
    "muted": "#94a3b8",
    "orange": "#f59e0b",
    "green": "#22c55e",
    "red": "#ef4444",
    "blue": "#38bdf8",
    "violet": "#8b5cf6",
}

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = str(DATA_DIR / "users.db")
INVITE_CODE = "2FEXC2026"

st.markdown(
    f"""
    <style>
    .stApp {{ background: {THEME['bg']}; color: {THEME['text']}; }}
    [data-testid="stHeader"] {{ background: rgba(5,7,13,.92); }}
    [data-testid="stSidebar"] {{ background: #05070d; border-right: 1px solid #1f2937; }}
    .block-container {{ padding-top: .8rem; padding-bottom: 1rem; max-width: 1800px; }}
    div[data-testid="metric-container"] {{ background: linear-gradient(180deg, {THEME['panel']}, {THEME['panel2']}); border: 1px solid #1f2937; padding: 10px; border-radius: 10px; }}
    .panel {{ background: linear-gradient(180deg, #0b1220, #101827); border: 1px solid #1f2937; border-radius: 12px; padding: 14px 16px; }}
    .terminal-title {{ color: {THEME['orange']}; font-size: 11px; letter-spacing: .14em; text-transform: uppercase; margin-bottom: 8px; font-weight:700; }}
    .subtle {{ color: {THEME['muted']}; font-size: 12px; }}
    .watch-row {{ display:flex; justify-content:space-between; gap:10px; border-bottom:1px solid #1f2937; padding:7px 0; font-family:monospace; font-size:13px; }}
    .watch-row:last-child {{ border-bottom:none; }}
    .hero {{ background: radial-gradient(circle at top left, rgba(56,189,248,.14), transparent 35%), linear-gradient(135deg, #0b1220 0%, #101827 70%); border:1px solid #1f2937; border-radius:14px; padding:22px; }}
    .auth-wrap {{ background: linear-gradient(180deg, #0b1220, #101827); border:1px solid #1f2937; border-radius:14px; padding:18px; min-height: 430px; }}
    h1,h2,h3 {{ color: {THEME['text']}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

CRYPTO_UNIVERSE = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",
    "BNB-USD": "BNB",
    "XRP-USD": "XRP",
    "DOGE-USD": "Dogecoin",
    "ADA-USD": "Cardano",
    "AVAX-USD": "Avalanche",
    "LINK-USD": "Chainlink",
    "MATIC-USD": "Polygon",
}
INTERVAL_MAP = {"15m": "15m", "1h": "60m", "4h": "1h", "1d": "1d"}
PERIOD_MAP = {"15m": "30d", "1h": "60d", "4h": "180d", "1d": "1y"}

TV_SYMBOL_MAP = {
    "BTC-USD": "BINANCE:BTCUSDT",
    "ETH-USD": "BINANCE:ETHUSDT",
    "SOL-USD": "BINANCE:SOLUSDT",
    "BNB-USD": "BINANCE:BNBUSDT",
    "XRP-USD": "BINANCE:XRPUSDT",
    "DOGE-USD": "BINANCE:DOGEUSDT",
    "ADA-USD": "BINANCE:ADAUSDT",
    "AVAX-USD": "BINANCE:AVAXUSDT",
    "LINK-USD": "BINANCE:LINKUSDT",
    "MATIC-USD": "BINANCE:POLUSDT",
}
TV_INTERVAL_MAP = {"15m": "15", "1h": "60", "4h": "240", "1d": "D"}


def render_tradingview_widget(symbol: str, timeframe: str, height: int = 760):
    tv_symbol = TV_SYMBOL_MAP.get(symbol, "BINANCE:BTCUSDT")
    tv_interval = TV_INTERVAL_MAP.get(timeframe, "60")
    html = f"""
    <div class="tradingview-widget-container" style="height:{height}px;width:100%">
      <div id="tradingview_chart" style="height:{height}px;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
        new TradingView.widget({{
          "autosize": true,
          "symbol": "{tv_symbol}",
          "interval": "{tv_interval}",
          "timezone": "Etc/UTC",
          "theme": "dark",
          "style": "1",
          "locale": "en",
          "toolbar_bg": "#0b1220",
          "enable_publishing": false,
          "allow_symbol_change": true,
          "hide_top_toolbar": false,
          "hide_legend": false,
          "save_image": true,
          "studies": ["RSI@tv-basicstudies", "MACD@tv-basicstudies", "Volume@tv-basicstudies"],
          "container_id": "tradingview_chart"
        }});
      </script>
    </div>
    """
    components.html(html, height=height)


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            approved INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def valid_username(username: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_]{4,20}$", username))


def create_user(username: str, email: str, password: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, email, password_hash, role, approved, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (username, email.lower().strip(), hash_password(password), "user", 1, datetime.utcnow().isoformat()),
        )
        conn.commit()
        ok, msg = True, "Compte créé avec succès. Connecte-toi maintenant."
    except sqlite3.IntegrityError:
        ok, msg = False, "Username ou email déjà utilisé."
    conn.close()
    return ok, msg


def authenticate(login: str, password: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, email, password_hash, role, approved FROM users WHERE lower(username)=lower(?) OR lower(email)=lower(?)",
        (login.strip(), login.strip()),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if row[3] != hash_password(password):
        return None
    if row[5] != 1:
        return "pending"
    return {"id": row[0], "username": row[1], "email": row[2], "role": row[4]}


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def sma(s, n):
    return s.rolling(n).mean()


def atr(df, n=14):
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        (df["high"] - df["low"]).abs(),
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def rsi(series, n=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


def macd(series, fast=12, slow=26, signal=9):
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    line = fast_ema - slow_ema
    sig = ema(line, signal)
    hist = line - sig
    return line, sig, hist


def bollinger(series, n=20, mult=2.0):
    mid = sma(series, n)
    std = series.rolling(n).std()
    upper = mid + mult * std
    lower = mid - mult * std
    return mid, upper, lower


def dmi_adx(df, n=14, smooth=14):
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr_rma = tr.ewm(alpha=1/n, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/n, adjust=False).mean() / atr_rma.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/n, adjust=False).mean() / atr_rma.replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx = dx.ewm(alpha=1/smooth, adjust=False).mean()
    return plus_di.fillna(0), minus_di.fillna(0), adx.fillna(0)


def rolling_vwap(df):
    typical = (df["high"] + df["low"] + df["close"]) / 3
    cum_pv = (typical * df["volume"]).cumsum()
    cum_vol = df["volume"].replace(0, np.nan).cumsum()
    return (cum_pv / cum_vol).fillna(df["close"])


def grade_color(g):
    return {"S+": THEME["green"], "A": "#16a34a", "B": THEME["orange"], "SKIP": THEME["red"]}.get(g, THEME["muted"])


@st.cache_data(ttl=600)
def load_crypto(symbol: str, timeframe: str):
    interval = INTERVAL_MAP[timeframe]
    period = PERIOD_MAP[timeframe]
    data = yf.download(symbol, period=period, interval=interval, auto_adjust=False, progress=False, group_by="column")
    if data is None or data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        flat_cols = []
        for col in data.columns:
            parts = [str(x) for x in col if x is not None and str(x) != ""]
            flat_cols.append("_".join(parts).lower())
        data.columns = flat_cols
    else:
        data.columns = [str(c).lower() for c in data.columns]

    data = data.reset_index()
    data.columns = [str(c).lower() for c in data.columns]

    date_candidates = [c for c in data.columns if c in ["date", "datetime", "index"] or c.startswith("date") or c.startswith("datetime")]
    if not date_candidates:
        return pd.DataFrame()
    date_col = date_candidates[0]
    data = data.rename(columns={date_col: "date"})

    value_map = {}
    for base in ["open", "high", "low", "close", "volume"]:
        matches = [c for c in data.columns if c == base or c.startswith(base + "_")]
        if matches:
            value_map[base] = matches[0]

    needed = ["open", "high", "low", "close", "volume"]
    if not all(k in value_map for k in needed):
        return pd.DataFrame()

    out = data[["date", value_map["open"], value_map["high"], value_map["low"], value_map["close"], value_map["volume"]]].copy()
    out.columns = ["date", "open", "high", "low", "close", "volume"]
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    for c in ["open", "high", "low", "close", "volume"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna().reset_index(drop=True)
    return out


def enrich_mega(df: pd.DataFrame, capital=300.0, max_dd_pct=20.0, ks_daily_pct=4.0, kelly_wr=0.55, kelly_rr=2.0,
                leverage_scalp=10, leverage_swing=7, leverage_brk=15, atr_len=14, adx_len=14, adx_smooth=14,
                bb_len=20, bb_mult=2.0, regime_trend_adx=25.0, regime_vol_atr=1.5, rsi_len=14, macd_fast=12,
                macd_slow=26, macd_sig=9, ema_fast_len=20, ema_slow_len=50, ema_trend_len=200, vol_lookback=20,
                vol_spike_mult=1.5, swing_len=5, timeframe='1h'):
    x = df.copy()
    if x.empty:
        return x

    x["atr_val"] = atr(x, atr_len)
    x["atr_avg"] = sma(x["atr_val"], 50)
    x["vol_expand"] = x["atr_val"] > x["atr_avg"] * regime_vol_atr
    x["diplus"], x["diminus"], x["adx_val"] = dmi_adx(x, adx_len, adx_smooth)
    x["strong_trend"] = x["adx_val"] > regime_trend_adx
    x["bb_mid"], x["bb_upper"], x["bb_lower"] = bollinger(x["close"], bb_len, bb_mult)
    x["bb_width"] = (x["bb_upper"] - x["bb_lower"]) / x["bb_mid"].replace(0, np.nan) * 100
    x["bb_avg_w"] = sma(x["bb_width"], 50)
    x["bb_squeeze"] = x["bb_width"] < x["bb_avg_w"] * 0.75

    x["regime"] = np.where(
        x["adx_val"] > regime_trend_adx * 1.3, "TREND",
        np.where((x["strong_trend"]) & (~x["vol_expand"]), "TREND",
                 np.where(x["vol_expand"], "VOLATILE", "RANGE"))
    )
    x["regime_score"] = x["regime"].map({"TREND": 2, "VOLATILE": 1, "RANGE": 0})

    x["rsi_val"] = rsi(x["close"], rsi_len)
    x["macd_line"], x["sig_line"], x["hist_val"] = macd(x["close"], macd_fast, macd_slow, macd_sig)
    x["ema_fast"] = ema(x["close"], ema_fast_len)
    x["ema_slow"] = ema(x["close"], ema_slow_len)
    x["ema_trend"] = ema(x["close"], ema_trend_len)
    x["vol_avg"] = sma(x["volume"], vol_lookback)
    x["rvol"] = np.where(x["vol_avg"] > 0, x["volume"] / x["vol_avg"], 0.0)
    x["vwap_val"] = rolling_vwap(x)
    x["swing_hi"] = x["high"].shift(1).rolling(swing_len).max()
    x["swing_lo"] = x["low"].shift(1).rolling(swing_len).min()
    x["prev_hi"] = x["high"].shift(1).rolling(swing_len * 3).max()
    x["prev_lo"] = x["low"].shift(1).rolling(swing_len * 3).min()

    x["di_bull"] = x["diplus"] > x["diminus"]
    x["di_bear"] = x["diminus"] > x["diplus"]

    x["gate1_bull"] = (x["ema_fast"] > x["ema_slow"]) & (x["close"] > x["ema_trend"]) & x["di_bull"]
    x["gate1_bear"] = (x["ema_fast"] < x["ema_slow"]) & (x["close"] < x["ema_trend"]) & x["di_bear"]
    x["gate2_bull"] = (x["rsi_val"] > 50) & (x["rsi_val"] < 80)
    x["gate2_bear"] = (x["rsi_val"] < 50) & (x["rsi_val"] > 20)
    x["gate3_bull"] = (x["macd_line"] > x["sig_line"]) & (x["hist_val"] > 0)
    x["gate3_bear"] = (x["macd_line"] < x["sig_line"]) & (x["hist_val"] < 0)
    x["gate4_pass"] = x["rvol"] > vol_spike_mult
    x["gate5_bull"] = x["close"] > x["vwap_val"]
    x["gate5_bear"] = x["close"] < x["vwap_val"]
    x["gate6_bull"] = (x["high"] >= x["swing_hi"]) & (x["low"] > x["prev_lo"])
    x["gate6_bear"] = (x["low"] <= x["swing_lo"]) & (x["high"] < x["prev_hi"])
    x["gate7_pass"] = (x["regime"] == "TREND") | ((x["regime"] == "VOLATILE") & (x["adx_val"] > 20))

    gates = [
        x["gate1_bull"] | x["gate1_bear"],
        x["gate2_bull"] | x["gate2_bear"],
        x["gate3_bull"] | x["gate3_bear"],
        x["gate4_pass"],
        x["gate5_bull"] | x["gate5_bear"],
        x["gate6_bull"] | x["gate6_bear"],
        x["gate7_pass"],
    ]
    x["total_gates"] = sum(g.astype(int) for g in gates)
    x["bull_count"] = x[["gate1_bull", "gate2_bull", "gate3_bull", "gate5_bull", "gate6_bull"]].sum(axis=1)
    x["bear_count"] = x[["gate1_bear", "gate2_bear", "gate3_bear", "gate5_bear", "gate6_bear"]].sum(axis=1)
    x["is_long"] = x["bull_count"] > x["bear_count"]
    x["is_short"] = x["bear_count"] > x["bull_count"]
    x["grade"] = np.where((x["total_gates"] >= 6) & (x["regime_score"] >= 1), "S+",
                   np.where(x["total_gates"] >= 5, "A",
                   np.where(x["total_gates"] >= 4, "B", "SKIP")))
    x["is_actionable"] = x["grade"].isin(["S+", "A"])

    tf_seconds = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}.get(timeframe, 3600)
    x["sleeve"] = np.where(tf_seconds <= 900, "SCALP", np.where(tf_seconds <= 14400, "SWING", "BREAKOUT"))
    x["lev"] = np.where(x["sleeve"] == "SCALP", leverage_scalp, np.where(x["sleeve"] == "SWING", leverage_swing, leverage_brk))
    x["sleeve_pct"] = np.where(x["sleeve"] == "SCALP", 0.40, np.where(x["sleeve"] == "SWING", 0.35, 0.25))
    x["sleeve_cap"] = capital * x["sleeve_pct"]

    kelly_full = (kelly_wr * kelly_rr - (1.0 - kelly_wr)) / kelly_rr
    kelly_quarter = max(kelly_full * 0.25, 0.01)
    x["risk_usdt"] = x["sleeve_cap"] * kelly_quarter
    x["position_usdt"] = x["risk_usdt"] * x["lev"]

    x["sl_mult"] = np.where(x["sleeve"] == "SCALP", 1.0, np.where(x["sleeve"] == "SWING", 1.5, 2.0))
    x["sl_dist"] = x["atr_val"] * x["sl_mult"]
    x["tp_dist"] = x["sl_dist"] * kelly_rr
    x["entry_price"] = x["close"]
    x["sl_price"] = np.where(x["is_long"], x["entry_price"] - x["sl_dist"], x["entry_price"] + x["sl_dist"])
    x["tp_price"] = np.where(x["is_long"], x["entry_price"] + x["tp_dist"], x["entry_price"] - x["tp_dist"])
    x["sl_pct"] = x["sl_dist"] / x["entry_price"] * 100
    x["tp_pct"] = x["tp_dist"] / x["entry_price"] * 100
    x["contracts"] = np.where(x["entry_price"] > 0, x["position_usdt"] / x["entry_price"], 0.0)
    x["notional"] = x["position_usdt"] * x["lev"]

    x["daily_open"] = x["close"].shift(1).rolling(24).first() if timeframe in ["1h", "15m"] else x["open"]
    x["daily_open"] = x["daily_open"].fillna(x["open"])
    x["daily_chg"] = np.where(x["daily_open"] > 0, (x["close"] - x["daily_open"]) / x["daily_open"] * 100, 0.0)
    x["kill_switch"] = x["daily_chg"] < -ks_daily_pct

    x["side"] = np.where(x["is_long"], "LONG", np.where(x["is_short"], "SHORT", "FLAT"))
    x["prev_side"] = x["side"].shift(1).fillna("FLAT")
    x["new_signal"] = (x["side"] != "FLAT") & (x["side"] != x["prev_side"])
    x["fire_long"] = x["is_actionable"] & x["is_long"] & ~x["kill_switch"] & ~x["is_short"] & x["new_signal"]
    x["fire_short"] = x["is_actionable"] & x["is_short"] & ~x["kill_switch"] & ~x["is_long"] & x["new_signal"]
    x["fire_any"] = x["fire_long"] | x["fire_short"]
    return x


def fmt_num(v, n=2):
    if pd.isna(v):
        return "-"
    return f"{v:,.{n}f}"


def fmt_pct(v):
    if pd.isna(v):
        return "-"
    return f"{v:+.2f}%"


def terminal_table(rows):
    html = ''.join([f"<div class='watch-row'><span>{k}</span><span>{v}</span></div>" for k, v in rows])
    st.markdown(f"<div class='panel'>{html}</div>", unsafe_allow_html=True)


def make_main_chart(df, symbol):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.58, 0.18, 0.24], vertical_spacing=0.04,
                        subplot_titles=(f"{symbol} Price", "Volume", "MEGA-ENT Momentum"))
    fig.add_trace(go.Candlestick(x=df["date"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
                                 increasing_line_color="#22c55e", decreasing_line_color="#ef4444", name="OHLC"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema_fast"], line=dict(color="#22c55e", width=1.2), name="EMA Fast"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema_slow"], line=dict(color="#f59e0b", width=1.2), name="EMA Slow"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["ema_trend"], line=dict(color="#cbd5e1", width=1.4), name="EMA 200"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["vwap_val"], line=dict(color="#fde047", width=1), name="VWAP"), row=1, col=1)

    green = df[df["close"] >= df["open"]]
    red = df[df["close"] < df["open"]]
    fig.add_trace(go.Bar(x=green["date"], y=green["volume"], marker_color="#14532d", name="Up Vol"), row=2, col=1)
    fig.add_trace(go.Bar(x=red["date"], y=red["volume"], marker_color="#7f1d1d", name="Down Vol"), row=2, col=1)

    fig.add_trace(go.Bar(x=df["date"], y=df["hist_val"], marker_color=np.where(df["hist_val"] >= 0, "#22c55e", "#ef4444"), name="MACD Hist"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df["date"], y=df["rsi_val"], line=dict(color="#38bdf8", width=1.4), name="RSI"), row=3, col=1)

    long_df = df[df["fire_long"]]
    short_df = df[df["fire_short"]]
    fig.add_trace(go.Scatter(x=long_df["date"], y=long_df["low"] * 0.995, mode="markers+text", text=long_df["grade"],
                             textposition="top center", marker=dict(color="#22c55e", size=9, symbol="triangle-up"), name="LONG"), row=1, col=1)
    fig.add_trace(go.Scatter(x=short_df["date"], y=short_df["high"] * 1.005, mode="markers+text", text=short_df["grade"],
                             textposition="bottom center", marker=dict(color="#ef4444", size=9, symbol="triangle-down"), name="SHORT"), row=1, col=1)

    fig.update_layout(height=920, paper_bgcolor=THEME["panel"], plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"]),
                      margin=dict(l=8, r=8, t=30, b=8), xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.02, x=0.01))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor=THEME["grid"])
    return fig


def make_compare_chart(symbol_returns):
    fig = go.Figure()
    for symbol, series in symbol_returns.items():
        fig.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines", name=symbol))
    fig.update_layout(height=340, paper_bgcolor=THEME["panel"], plot_bgcolor=THEME["panel"], font=dict(color=THEME["text"]), margin=dict(l=8, r=8, t=24, b=8))
    fig.update_yaxes(ticksuffix="%", showgrid=True, gridcolor=THEME["grid"])
    fig.update_xaxes(showgrid=False)
    return fig


def login_view():
    st.title("2FEXC V2")
    st.caption("Crypto terminal with login access.")
    left, right = st.columns([1.15, 1])
    with left:
        st.markdown(
            """
            <div class='hero'>
                <div class='terminal-title'>Access gateway</div>
                <h2 style='margin:0 0 10px 0'>Bienvenue sur 2FEXC</h2>
                <p style='color:#94a3b8'>Connecte-toi ou crée un compte pour accéder au terminal crypto et au moteur de signaux MEGA-ENTONNOIR.</p>
                <div style='height:10px'></div>
                <div class='watch-row'><span>Modules</span><span>Monitor · Charts · Signals · Screeners</span></div>
                <div class='watch-row'><span>Universe</span><span>BTC · ETH · SOL · BNB · XRP · ADA</span></div>
                <div class='watch-row'><span>Invite code</span><span>2FEXC2026</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        tabs = st.tabs(["Connexion", "Inscription"])
        with tabs[0]:
            st.markdown("<div class='auth-wrap'>", unsafe_allow_html=True)
            login = st.text_input("Username ou email", key="login_user")
            password = st.text_input("Mot de passe", type="password", key="login_pass")
            if st.button("Se connecter", use_container_width=True):
                result = authenticate(login, password)
                if result:
                    st.session_state.authenticated = True
                    st.session_state.user = result
                    st.rerun()
                else:
                    st.error("Identifiants invalides.")
            st.markdown("</div>", unsafe_allow_html=True)
        with tabs[1]:
            st.markdown("<div class='auth-wrap'>", unsafe_allow_html=True)
            username = st.text_input("Username", key="signup_user")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Mot de passe", type="password", key="signup_pass")
            confirm = st.text_input("Confirmer le mot de passe", type="password", key="signup_confirm")
            invite = st.text_input("Code d'invitation", key="signup_invite")
            if st.button("Créer un compte", use_container_width=True):
                if not valid_username(username):
                    st.error("Username invalide. Utilise 4 à 20 caractères: lettres, chiffres ou underscore.")
                elif not valid_email(email):
                    st.error("Email invalide.")
                elif len(password) < 8:
                    st.error("Mot de passe trop court. Minimum 8 caractères.")
                elif password != confirm:
                    st.error("Les mots de passe ne correspondent pas.")
                elif invite.strip() != INVITE_CODE:
                    st.error("Code d'invitation invalide.")
                else:
                    ok, msg = create_user(username.strip(), email.strip(), password)
                    st.success(msg) if ok else st.error(msg)
            st.markdown("</div>", unsafe_allow_html=True)


def dashboard_view():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    with st.sidebar:
        st.markdown("## 2FEXC V2")
        st.caption(f"Connecté : {st.session_state.user['username']}")
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()
        st.markdown("---")
        symbol = st.selectbox("Symbol", options=list(CRYPTO_UNIVERSE.keys()), index=0)
        timeframe = st.selectbox("Timeframe", options=["15m", "1h", "4h", "1d"], index=1)
        lookback = st.slider("Bars affichées", 80, 500, 220, 20)
        st.markdown("---")
        capital = st.number_input("Capital USDT", 50.0, 100000.0, 300.0, step=50.0)
        kelly_wr = st.slider("Kelly Win Rate", 0.10, 0.95, 0.55, 0.01)
        kelly_rr = st.slider("Kelly R:R", 0.5, 5.0, 2.0, 0.1)
        ks_daily_pct = st.slider("Kill Switch %", 0.5, 10.0, 4.0, 0.5)
        st.markdown("---")
        watch = st.multiselect("Monitor list", options=list(CRYPTO_UNIVERSE.keys()), default=["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD"])

    raw = load_crypto(symbol, timeframe)
    if raw.empty:
        st.error("Impossible de charger les données pour ce symbole.")
        return
    df = enrich_mega(raw, capital=capital, kelly_wr=kelly_wr, kelly_rr=kelly_rr, ks_daily_pct=ks_daily_pct, timeframe=timeframe).tail(lookback).copy()
    last = df.iloc[-1]

    st.title("2FEXC V2")
    st.caption("Crypto terminal V2 with dense market monitor and MEGA-ENTONNOIR signal engine for manual trading.")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric(symbol, fmt_num(last["close"]), fmt_pct((last["close"] / df.iloc[-2]["close"] - 1) * 100 if len(df) > 1 else 0))
    m2.metric("Signal", f"{last['side']} {last['grade']}")
    m3.metric("Regime", last["regime"])
    m4.metric("Gates", f"{int(last['total_gates'])}/7")
    m5.metric("RSI", fmt_num(last["rsi_val"]))
    m6.metric("RVOL", fmt_num(last["rvol"]))

    tabs = st.tabs(["Monitor", "Chart & Signals", "Screeners", "Cross-Asset", "Signal Board"])

    with tabs[0]:
        c1, c2, c3 = st.columns([1.15, 1.8, 1.1])
        with c1:
            st.markdown('<div class="terminal-title">Symbol monitor</div>', unsafe_allow_html=True)
            terminal_table([
                ("Symbol", symbol),
                ("Name", CRYPTO_UNIVERSE.get(symbol, symbol)),
                ("Timeframe", timeframe),
                ("Last", fmt_num(last["close"])),
                ("Regime", last["regime"]),
                ("Signal", f"{last['side']} {last['grade']}"),
                ("Sleeve", f"{last['sleeve']} {int(last['lev'])}x"),
                ("Risk USDT", fmt_num(last["risk_usdt"])),
                ("Position", fmt_num(last["position_usdt"])),
                ("Notional", fmt_num(last["notional"])),
                ("Contracts", fmt_num(last["contracts"], 4)),
                ("Kill Switch", "ON" if last["kill_switch"] else "OFF"),
            ])
        with c2:
            st.markdown('<div class="terminal-title">TradingView chart</div>', unsafe_allow_html=True)
            render_tradingview_widget(symbol, timeframe, height=760)
        with c3:
            st.markdown('<div class="terminal-title">Execution levels</div>', unsafe_allow_html=True)
            terminal_table([
                ("Entry", fmt_num(last["entry_price"])),
                ("Stop", fmt_num(last["sl_price"])),
                ("Target", fmt_num(last["tp_price"])),
                ("SL %", fmt_num(last["sl_pct"])),
                ("TP %", fmt_num(last["tp_pct"])),
                ("ADX", fmt_num(last["adx_val"])),
                ("Daily %", fmt_pct(last["daily_chg"])),
                ("EMA Fast", fmt_num(last["ema_fast"])),
                ("EMA Slow", fmt_num(last["ema_slow"])),
                ("EMA Trend", fmt_num(last["ema_trend"])),
                ("VWAP", fmt_num(last["vwap_val"])),
                ("BB Width", fmt_num(last["bb_width"])),
            ])

    with tabs[1]:
        t1, t2 = st.columns([2.1, 1])
        with t1:
            st.markdown('<div class="terminal-title">TradingView main chart</div>', unsafe_allow_html=True)
            render_tradingview_widget(symbol, timeframe, height=820)
            st.markdown('<div class="terminal-title">MEGA-ENT overlays and internal engine</div>', unsafe_allow_html=True)
            st.plotly_chart(make_main_chart(df, symbol), use_container_width=True)
        with t2:
            st.markdown('<div class="terminal-title">MEGA-ENT detail</div>', unsafe_allow_html=True)
            gate_rows = [
                ("Gate 1 Trend", "PASS" if (last["gate1_bull"] or last["gate1_bear"]) else "FAIL"),
                ("Gate 2 RSI", "PASS" if (last["gate2_bull"] or last["gate2_bear"]) else "FAIL"),
                ("Gate 3 MACD", "PASS" if (last["gate3_bull"] or last["gate3_bear"]) else "FAIL"),
                ("Gate 4 Volume", "PASS" if last["gate4_pass"] else "FAIL"),
                ("Gate 5 VWAP", "PASS" if (last["gate5_bull"] or last["gate5_bear"]) else "FAIL"),
                ("Gate 6 Breakout", "PASS" if (last["gate6_bull"] or last["gate6_bear"]) else "FAIL"),
                ("Gate 7 Regime", "PASS" if last["gate7_pass"] else "FAIL"),
                ("Bull Count", int(last["bull_count"])),
                ("Bear Count", int(last["bear_count"])),
                ("Grade", last["grade"]),
                ("Side", last["side"]),
            ]
            terminal_table(gate_rows)
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            st.markdown('<div class="terminal-title">Signal tape</div>', unsafe_allow_html=True)
            signal_df = df[df["fire_any"]][["date", "grade", "side", "regime", "total_gates", "entry_price", "sl_price", "tp_price"]].tail(15)
            st.dataframe(signal_df, use_container_width=True, hide_index=True)

    with tabs[2]:
        screener_rows = []
        progress = st.progress(0, text="Scanning crypto universe...")
        for i, sym in enumerate(CRYPTO_UNIVERSE.keys()):
            temp = load_crypto(sym, timeframe)
            if temp.empty:
                continue
            edf = enrich_mega(temp, capital=capital, kelly_wr=kelly_wr, kelly_rr=kelly_rr, ks_daily_pct=ks_daily_pct, timeframe=timeframe).tail(250)
            r = edf.iloc[-1]
            prev_close = edf.iloc[-2]["close"] if len(edf) > 1 else r["close"]
            screener_rows.append({
                "Symbol": sym,
                "Last": r["close"],
                "Day %": (r["close"] / prev_close - 1) * 100,
                "Grade": r["grade"],
                "Side": r["side"],
                "Regime": r["regime"],
                "Gates": int(r["total_gates"]),
                "RSI": r["rsi_val"],
                "ADX": r["adx_val"],
                "RVOL": r["rvol"],
                "Signal": bool(r["fire_any"]),
            })
            progress.progress((i + 1) / len(CRYPTO_UNIVERSE), text=f"Scanning {sym}...")

        progress.empty()
        screener_df = pd.DataFrame(screener_rows).sort_values(["Signal", "Gates", "RVOL"], ascending=[False, False, False])
        st.markdown('<div class="terminal-title">Crypto screener</div>', unsafe_allow_html=True)
        st.dataframe(screener_df, use_container_width=True, hide_index=True)

    with tabs[3]:
        returns = {}
        snap_rows = []
        for sym in watch:
            temp = load_crypto(sym, timeframe)
            if temp.empty:
                continue
            edf = enrich_mega(temp, capital=capital, kelly_wr=kelly_wr, kelly_rr=kelly_rr, ks_daily_pct=ks_daily_pct, timeframe=timeframe).tail(120)
            base = edf["close"].iloc[0]
            returns[sym] = (edf.set_index("date")["close"] / base - 1) * 100
            r = edf.iloc[-1]
            snap_rows.append({
                "Symbol": sym,
                "Grade": r["grade"],
                "Side": r["side"],
                "Regime": r["regime"],
                "RSI": round(r["rsi_val"], 2),
                "ADX": round(r["adx_val"], 2),
                "RVOL": round(r["rvol"], 2),
                "Entry": round(r["entry_price"], 4),
            })
        c1, c2 = st.columns([1.6, 1])
        with c1:
            st.markdown('<div class="terminal-title">Relative performance</div>', unsafe_allow_html=True)
            if returns:
                st.plotly_chart(make_compare_chart(returns), use_container_width=True)
        with c2:
            st.markdown('<div class="terminal-title">Market snapshot</div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(snap_rows), use_container_width=True, hide_index=True)

    with tabs[4]:
        history = df[df["fire_any"]].copy()
        if history.empty:
            st.info("No actionable signals on current loaded sample.")
        else:
            out = history[["date", "close", "grade", "side", "regime", "total_gates", "risk_usdt", "position_usdt", "notional", "sl_price", "tp_price"]].tail(40)
            st.markdown('<div class="terminal-title">Recent actionable signals</div>', unsafe_allow_html=True)
            st.dataframe(out, use_container_width=True, hide_index=True)


init_db()
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.authenticated and st.session_state.user:
    dashboard_view()
else:
    login_view()
