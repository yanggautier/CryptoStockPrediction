"""
Crypto Predict — Data Collector
================================
Collecte :
  - OHLCV via yfinance
  - Indicateurs techniques (RSI, MACD, Bollinger)
  - Fear & Greed Index (alternative.me)
  - Macro : DXY, SP500, NASDAQ, Gold, Oil, VIX (yfinance)
  - Funding Rate + Open Interest (Binance API, gratuit)
  - Sentiment CryptoPanic (optionnel)
"""

import os, time, logging, requests
import pandas as pd
import numpy as np
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SYMBOLS = {
    "BTCUSDT": "BTC-USD",
    "ETHUSDT": "ETH-USD",
    "BNBUSDT": "BNB-USD",
    "SOLUSDT": "SOL-USD",
    "XRPUSDT": "XRP-USD",
}

MACRO_TICKERS = {
    "dxy":    "DX-Y.NYB",   # Dollar Index
    "sp500":  "^GSPC",      # S&P 500
    "nasdaq": "^IXIC",      # NASDAQ
    "gold":   "GC=F",       # Gold Futures
    "oil":    "CL=F",       # WTI Oil
    "vix":    "^VIX",       # Volatility Index
}

PERIOD   = "max"
INTERVAL = "1d"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CRYPTOPANIC_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")


# ──────────────────────────────────────────────
# OHLCV + INDICATEURS TECHNIQUES
# ──────────────────────────────────────────────

def fetch_ohlcv(symbol: str) -> pd.DataFrame:
    ticker = SYMBOLS[symbol]
    log.info(f"Téléchargement {symbol} ({ticker})...")
    df = yf.download(ticker, period=PERIOD, interval=INTERVAL,
                     auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"Aucune donnée pour {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns   = [c.lower() for c in df.columns]
    df.index.name = "timestamp"
    df["symbol"] = symbol
    df = df[["open", "high", "low", "close", "volume", "symbol"]].dropna()
    log.info(f"{symbol} — {len(df)} lignes ({df.index[0].date()} → {df.index[-1].date()})")
    return df


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close, volume = df["close"], df["volume"]
    df["rsi"]        = RSIIndicator(close=close, window=14).rsi()
    macd = MACD(close=close)
    df["macd"]       = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_diff"]  = macd.macd_diff()
    bb = BollingerBands(close=close, window=20, window_dev=2)
    df["bb_upper"]   = bb.bollinger_hband()
    df["bb_middle"]  = bb.bollinger_mavg()
    df["bb_lower"]   = bb.bollinger_lband()
    df["bb_width"]   = bb.bollinger_wband()
    df["price_ma7"]  = close.rolling(7).mean()
    df["price_ma30"] = close.rolling(30).mean()
    df["price_ma90"] = close.rolling(90).mean()
    df["volume_ma7"] = volume.rolling(7).mean()
    df["returns"]     = close.pct_change()
    df["log_returns"] = close.pct_change().add(1).apply("log")
    df["volatility"]  = df["returns"].rolling(14).std()
    df["target_direction"] = (close.shift(-3) > close * 1.02).astype(int)
    df["target_price"]     = close.shift(-3)
    df.dropna(inplace=True)
    return df


# ──────────────────────────────────────────────
# FEAR & GREED
# ──────────────────────────────────────────────

def fetch_fear_greed(limit: int = 3000) -> pd.DataFrame:
    log.info("Téléchargement Fear & Greed Index...")
    resp = requests.get(
        f"https://api.alternative.me/fng/?limit={limit}&format=json",
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    df   = pd.DataFrame(data)[["timestamp", "value", "value_classification"]]
    df["timestamp"]       = pd.to_datetime(df["timestamp"].astype(int), unit="s")
    df["fear_greed"]      = df["value"].astype(int)
    df["fear_greed_norm"] = df["fear_greed"] / 100.0
    df.set_index("timestamp", inplace=True)
    df.index = df.index.normalize()
    log.info(f"Fear & Greed — {len(df)} jours")
    return df[["fear_greed", "fear_greed_norm"]]


# ──────────────────────────────────────────────
# MACRO DATA (DXY, SP500, Gold, VIX...)
# ──────────────────────────────────────────────

def fetch_macro() -> pd.DataFrame:
    """Collecte les données macro via yfinance."""
    log.info("Téléchargement données macro...")
    dfs = {}
    for name, ticker in MACRO_TICKERS.items():
        try:
            raw = yf.download(ticker, period=PERIOD, interval=INTERVAL,
                              auto_adjust=True, progress=False)
            if raw.empty:
                log.warning(f"Macro {name} ({ticker}) : données vides")
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            raw.columns   = [c.lower() for c in raw.columns]
            raw.index.name = "timestamp"
            raw.index      = raw.index.normalize()
            series         = raw["close"].rename(name)
            dfs[name]      = series
            log.info(f"  {name} ({ticker}) : {len(series)} lignes")
            time.sleep(0.3)
        except Exception as e:
            log.warning(f"Macro {name} ({ticker}) erreur : {e}")

    if not dfs:
        log.warning("Aucune donnée macro collectée")
        return pd.DataFrame()

    macro = pd.concat(dfs.values(), axis=1)

    # Rendements journaliers
    for col in ["dxy", "sp500", "nasdaq", "gold", "oil"]:
        if col in macro.columns:
            macro[f"{col}_returns"] = macro[col].pct_change(fill_method=None)

    macro.ffill(inplace=True)
    log.info(f"Macro — {len(macro)} lignes x {len(macro.columns)} colonnes")
    return macro


# ──────────────────────────────────────────────
# FUNDING RATE + OPEN INTEREST (Binance, gratuit)
# ──────────────────────────────────────────────

def fetch_funding_rate(symbol: str, limit: int = 1000) -> pd.DataFrame:
    """Funding rate Binance Futures — signal sentiment traders."""
    sym = symbol.replace("USDT", "") + "USDT"
    try:
        resp = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": sym, "limit": limit},
            timeout=10
        )
        if resp.status_code != 200:
            return pd.DataFrame()
        data = resp.json()
        df   = pd.DataFrame(data)
        df["timestamp"]    = pd.to_datetime(df["fundingTime"], unit="ms")
        df["funding_rate"] = df["fundingRate"].astype(float)
        df.set_index("timestamp", inplace=True)
        df.index = df.index.normalize()
        # Moyenne journalière (3 paiements/jour)
        daily = df["funding_rate"].resample("1D").mean().rename("funding_rate")
        log.info(f"Funding rate {symbol} — {len(daily)} jours")
        return daily.to_frame()
    except Exception as e:
        log.warning(f"Funding rate {symbol} : {e}")
        return pd.DataFrame()


# ──────────────────────────────────────────────
# CRYPTOPANIC SENTIMENT (optionnel)
# ──────────────────────────────────────────────

def fetch_cryptopanic_sentiment(symbol: str) -> float:
    """Score sentiment CryptoPanic [-1, +1]. Nécessite une clé API gratuite."""
    if not CRYPTOPANIC_KEY:
        return 0.0
    currency = symbol.replace("USDT", "")
    try:
        resp = requests.get(
            "https://cryptopanic.com/api/v1/posts/",
            params={
                "auth_token": CRYPTOPANIC_KEY,
                "currencies":  currency,
                "kind":        "news",
                "public":      "true",
            },
            timeout=10
        ).json()
        results = resp.get("results", [])
        if not results:
            return 0.0
        scores = []
        for post in results[:20]:
            votes = post.get("votes", {})
            pos   = votes.get("positive", 0) + votes.get("liked", 0)
            neg   = votes.get("negative", 0) + votes.get("disliked", 0)
            total = pos + neg
            if total > 0:
                scores.append((pos - neg) / total)
        return round(sum(scores) / len(scores), 4) if scores else 0.0
    except Exception as e:
        log.warning(f"CryptoPanic {symbol} : {e}")
        return 0.0


# ──────────────────────────────────────────────
# PIPELINE COMPLET
# ──────────────────────────────────────────────

def build_dataset(symbol: str) -> pd.DataFrame:
    # 1. OHLCV + indicateurs
    df = fetch_ohlcv(symbol)
    df = add_technical_indicators(df)
    df.index = df.index.normalize()

    # 2. Fear & Greed
    try:
        fg = fetch_fear_greed()
        df = df.join(fg[["fear_greed", "fear_greed_norm"]], how="left")
        df["fear_greed"]      = df["fear_greed"].ffill()
        df["fear_greed_norm"] = df["fear_greed_norm"].ffill()
    except Exception as e:
        log.warning(f"Fear & Greed erreur : {e}")
    df["fear_greed"]      = df.get("fear_greed",      pd.Series(50,  index=df.index)).fillna(50)
    df["fear_greed_norm"] = df.get("fear_greed_norm", pd.Series(0.5, index=df.index)).fillna(0.5)

    # 3. Macro
    try:
        time.sleep(1)   # ← éviter rate limit yfinance
        macro = fetch_macro()
        if not macro.empty:
            df = df.join(macro, how="left")
            for col in macro.columns:
                if col in df.columns:
                    df[col].ffill(inplace=True)
                    df[col].fillna(0, inplace=True)
    except Exception as e:
        log.warning(f"Macro erreur : {e}")

    # 4. Funding Rate
    try:
        funding = fetch_funding_rate(symbol)
        if not funding.empty:
            df = df.join(funding, how="left")
            df["funding_rate"].ffill(inplace=True)
            df["funding_rate"].fillna(0, inplace=True)
    except Exception as e:
        log.warning(f"Funding rate erreur : {e}")

    # 5. Signaux macro dérivés — 100% défensif
    df["dxy_trend"]     = df["dxy"].pct_change(7).fillna(0)     if "dxy"           in df.columns else 0.0
    df["equity_regime"] = (df["sp500_returns"].rolling(20).mean() > 0).astype(int).fillna(0) if "sp500_returns" in df.columns else 0
    df["vix_high"]      = (df["vix"] > 20).astype(int).fillna(0) if "vix"          in df.columns else 0
    df["rate_pressure"] = df["funding_rate"].rolling(3).mean().fillna(0) if "funding_rate" in df.columns else 0.0

    log.info(f"{symbol} — {df.shape[0]} lignes x {df.shape[1]} colonnes")
    log.info(f"  Macro OK: { {c: df[c].notna().sum() for c in ['dxy_trend','equity_regime','vix_high','rate_pressure']} }")
    return df

def save_to_csv(df: pd.DataFrame, symbol: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{symbol}_1d.csv")
    df.to_csv(path)
    log.info(f"CSV sauvegardé : {path} ({len(df)} lignes)")


def run(save_mode: str = "csv"):
    log.info("=== Démarrage collecte complète ===")
    datasets = {}
    for symbol in SYMBOLS:
        try:
            df = build_dataset(symbol)
            datasets[symbol] = df
            if save_mode in ("csv", "both"):
                save_to_csv(df, symbol)
            time.sleep(1)
        except Exception as e:
            log.error(f"Erreur {symbol} : {e}")
    log.info(f"=== Collecte terminée — {len(datasets)}/{len(SYMBOLS)} symboles ===")
    return datasets


if __name__ == "__main__":
    datasets = run(save_mode="csv")
    btc = datasets.get("BTCUSDT")
    if btc is not None:
        print(f"\n=== BTCUSDT ({len(btc)} jours) ===")
        print(f"Colonnes ({len(btc.columns)}) : {list(btc.columns)}")
        macro_check = ["dxy", "sp500", "gold", "vix", "fear_greed_norm", "funding_rate"]
        for col in macro_check:
            if col in btc.columns:
                non_null = btc[col].notna().sum()
                print(f"  {col}: {non_null} valeurs non-nulles")