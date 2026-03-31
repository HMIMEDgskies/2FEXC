from pathlib import Path
import re
import sqlite3
import hashlib
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="2FEXC", page_icon="📺", layout="wide")

THEME = {
    "bg": "#0b0f14",
    "panel": "#111827",
    "panel2": "#0f172a",
    "grid": "#2a3441",
    "text": "#e5e7eb",
    "muted": "#94a3b8",
    "orange": "#f59e0b",
    "green": "#22c55e",
    "red": "#ef4444",
    "blue": "#38bdf8",
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
    [data-testid="stHeader"] {{ background: rgba(11,15,20,.88); }}
    [data-testid="stSidebar"] {{ background: #0a0d12; border-right: 1px solid #1f2937; }}
    .block-container {{ padding-top: 1rem; padding-bottom: 1rem; max-width: 1600px; }}
    div[data-testid="metric-container"] {{ background: linear-gradient(180deg, {THEME['panel']}, {THEME['panel2']}); border: 1px solid #1f2937; padding: 12px; border-radius: 10px; }}
    .terminal-card {{ background: linear-gradient(180deg, #111827, #0f172a); border: 1px solid #1f2937; border-radius: 12px; padding: 14px 16px; }}
    .terminal-title {{ color: {THEME['orange']}; font-size: 12px; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 8px; }}
    .terminal-sub {{ color: {THEME['muted']}; font-size: 12px; }}
    .watch-row {{ display:flex; justify-content:space-between; gap:12px; border-bottom: 1px solid #1f2937; padding: 8px 0; font-family: monospace; }}
    .watch-row:last-child {{ border-bottom:none; }}
    .hero {{ background: linear-gradient(135deg, #111827 0%, #0f172a 70%); border:1px solid #1f2937; border-radius:14px; padding:22px; }}
    .auth-wrap {{ background: linear-gradient(180deg, #111827, #0f172a); border:1px solid #1f2937; border-radius:14px; padding:18px; min-height: 430px; }}
    h1,h2,h3 {{ color: {THEME['text']}; }}
    </style>
    """,
    unsafe_allow_html=True,
)


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


@st.cache_data(ttl=900)
def generate_prices(seed: int = 42, periods: int = 260):
    rng = np.random.default_rng(seed)
    tickers = {
        "AAPL": 188.4,
        "MSFT": 427.2,
        "NVDA": 121.8,
        "SPY": 527.6,
        "BTC-USD": 84300.0,
        "CL=F": 78.9,
        "EURUSD=X": 1.08,
        "GC=F": 2310.0,
    }
    dates = pd.bdate_range(end=pd.Timestamp.utcnow().tz_localize(None), periods=periods)
    rows = []
    for ticker, start in tickers.items():
        vol = 0.012 if ticker not in ["BTC-USD", "CL=F", "GC=F"] else 0.02
        drift = 0.0004 if ticker not in ["CL=F", "EURUSD=X"] else 0.0001
        rets = rng.normal(drift, vol, len(dates))
        prices = start * np.exp(np.cumsum(rets))
        for d, p, r in zip(dates, prices, rets):
            rows.append([ticker, d, p, r])
    return pd.DataFrame(rows, columns=["ticker", "date", "close", "ret"])


@st.cache_data(ttl=900)
def build_news():
    now = datetime.now(timezone.utc)
    items = [
        ["Macro", "US rates path remains market driver for duration trades", now - timedelta(minutes=18)],
        ["Equities", "Mega-cap tech leadership narrows as semis pause after strong run", now - timedelta(minutes=43)],
        ["FX", "Dollar trades mixed with euro range-bound ahead of inflation data", now - timedelta(hours=1, minutes=5)],
        ["Energy", "Crude steady as traders balance inventory draws and growth concerns", now - timedelta(hours=2, minutes=10)],
        ["Crypto", "Bitcoin volatility cools while ETF-linked flows stay in focus", now - timedelta(hours=3, minutes=12)],
    ]
    return pd.DataFrame(items, columns=["topic", "headline", "time"])


def fmt(v):
    if abs(v) >= 1000:
        return f"{v:,.2f}"
    if abs(v) >= 10:
        return f"{v:,.2f}"
    return f"{v:,.4f}"


def pct(v):
    return f"{v*100:+.2f}%"


def chart_price(df_ticker, title):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_ticker["date"], y=df_ticker["close"], mode="lines", name=title, line=dict(color=THEME["orange"], width=2)))
    ma20 = df_ticker["close"].rolling(20).mean()
    fig.add_trace(go.Scatter(x=df_ticker["date"], y=ma20, mode="lines", name="MA20", line=dict(color=THEME["blue"], width=1.5, dash="dot")))
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor=THEME["panel"],
        plot_bgcolor=THEME["panel"],
        font=dict(color=THEME["text"]),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor=THEME["grid"]),
        legend=dict(orientation="h", y=1.02, x=0.01),
    )
    return fig


def chart_returns(returns):
    fig = go.Figure(
        go.Bar(
            x=returns.index,
            y=returns.values * 100,
            marker_color=[THEME["green"] if x >= 0 else THEME["red"] for x in returns.values],
        )
    )
    fig.update_layout(
        height=250,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor=THEME["panel"],
        plot_bgcolor=THEME["panel"],
        font=dict(color=THEME["text"]),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor=THEME["grid"], ticksuffix="%"),
    )
    return fig


def ensure_state():
    defaults = {"authenticated": False, "user": None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def login_view():
    st.title("2FEXC")
    st.caption("Private market terminal with access control.")
    left, right = st.columns([1.2, 1])

    with left:
        st.markdown(
            """
            <div class='hero'>
                <div class='terminal-title'>Access gateway</div>
                <h2 style='margin:0 0 10px 0'>Institutional-style market workspace</h2>
                <p style='color:#94a3b8'>Connexion obligatoire avant d'accéder au terminal. L'inscription crée un compte local dans SQLite. Tu peux ensuite pousser le repo sur GitHub et déployer sur Streamlit Cloud.</p>
                <div style='height:10px'></div>
                <div class='watch-row'><span>Modules</span><span>Watchlist · News · Charts · Macro</span></div>
                <div class='watch-row'><span>Security</span><span>Login · Signup · Session · Logout</span></div>
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
                if result == "pending":
                    st.warning("Compte créé mais non approuvé.")
                elif result:
                    st.session_state.authenticated = True
                    st.session_state.user = result
                    st.success(f"Bienvenue {result['username']}")
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
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)
            st.markdown("</div>", unsafe_allow_html=True)


def dashboard_view():
    df = generate_prices()
    news = build_news()
    latest = df.sort_values("date").groupby("ticker").tail(1).set_index("ticker")
    prev = df.sort_values("date").groupby("ticker").nth(-2)
    joined = latest.join(prev[["close"]], rsuffix="_prev")
    joined["chg"] = joined["close"] / joined["close_prev"] - 1

    with st.sidebar:
        st.markdown("## 2FEXC")
        st.caption(f"Connecté : {st.session_state.user['username']}")
        if st.button("Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()

        st.markdown("---")
        ticker = st.selectbox("Actif principal", options=list(joined.index), index=0)
        universe = st.multiselect("Watchlist", options=list(joined.index), default=list(joined.index)[:5])
        lookback = st.slider("Historique (jours)", 30, 260, 180, 10)

        st.markdown("---")
        st.markdown("### Sources futures")
        st.write("- yfinance")
        st.write("- FRED")
        st.write("- Finnhub / NewsAPI")
        st.write("- Polygon / Twelve Data")

    st.title("2FEXC")
    st.caption("Financial terminal prototype with protected access.")

    c1, c2, c3, c4 = st.columns(4)
    for col, t in zip([c1, c2, c3, c4], list(joined.index)[:4]):
        row = joined.loc[t]
        col.metric(t, fmt(row["close"]), pct(row["chg"]))

    left, right = st.columns([2.3, 1.2])
    sel = df[df["ticker"] == ticker].tail(lookback).copy()

    with left:
        st.markdown('<div class="terminal-title">Price monitor</div>', unsafe_allow_html=True)
        st.plotly_chart(chart_price(sel, ticker), use_container_width=True)
        monthly = sel.set_index("date")["close"].resample("M").last().pct_change().dropna().tail(8)
        st.markdown('<div class="terminal-title">Monthly performance</div>', unsafe_allow_html=True)
        st.plotly_chart(chart_returns(monthly), use_container_width=True)

    with right:
        st.markdown('<div class="terminal-title">Watchlist</div>', unsafe_allow_html=True)
        rows = []
        for t in universe:
            r = joined.loc[t]
            color = THEME["green"] if r["chg"] >= 0 else THEME["red"]
            rows.append(
                f'<div class="watch-row"><span>{t}</span><span>{fmt(r["close"])} <span style="color:{color}">{pct(r["chg"])}</span></span></div>'
            )
        st.markdown(f'<div class="terminal-card">{"".join(rows)}</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="terminal-title">News monitor</div>', unsafe_allow_html=True)
        news_html = "".join(
            [
                f'<div class="watch-row"><span>{r.topic}</span><span style="max-width:70%;text-align:right">{r.headline}</span></div>'
                for r in news.itertuples()
            ]
        )
        st.markdown(f'<div class="terminal-card">{news_html}</div>', unsafe_allow_html=True)

    st.markdown("## Cross-asset snapshot")
    heat = joined[["close", "chg"]].reset_index().rename(columns={"index": "ticker"})
    st.dataframe(
        heat[["ticker", "close", "chg"]].rename(columns={"ticker": "Ticker", "close": "Last", "chg": "Day %"}),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("## Account profile")
    st.json(
        {
            "username": st.session_state.user["username"],
            "email": st.session_state.user["email"],
            "role": st.session_state.user["role"],
        }
    )


init_db()
ensure_state()

if st.session_state.authenticated and st.session_state.user:
    dashboard_view()
else:
    login_view()
