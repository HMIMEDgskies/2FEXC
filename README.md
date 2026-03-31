# 2FEXC V2

2FEXC V2 est une app Streamlit orientée crypto pour trading manuel, avec login, inscription, dashboard dense, screener crypto et intégration Python du système MEGA-ENTONNOIR.

## Modules
- Login / Signup / Logout
- Monitor crypto multi-symboles
- Chart & Signals avec candlesticks, volume, RSI, MACD, EMA, VWAP
- Screener crypto
- Cross-asset monitor
- Signal board basé sur MEGA-ENTONNOIR

## Données
- Données de marché via `yfinance`
- Univers crypto initial : BTC, ETH, SOL, BNB, XRP, DOGE, ADA, AVAX, LINK, MATIC

## Lancer
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Note
- Le script Pine original n'est pas exécuté directement dans Streamlit ; il est réimplémenté en Python pour reproduire la logique de signal.
- SQLite est pratique pour V1/V2 locale mais pas idéal pour une prod multi-utilisateur durable.
