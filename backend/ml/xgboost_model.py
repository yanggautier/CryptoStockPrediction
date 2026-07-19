"""
Crypto Predict — XGBoost Model (sans MLflow)
"""
import os, logging
import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from xgboost import XGBClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, classification_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SYMBOL    = "BTCUSDT"
DATA_DIR  = os.path.join(os.path.dirname(__file__), "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

FEATURES = [
    "open", "high", "low", "close", "volume",
    "rsi", "macd", "macd_signal", "macd_diff",
    "bb_upper", "bb_middle", "bb_lower", "bb_width",
    "returns", "log_returns", "volatility",
    "price_ma7", "price_ma30", "price_ma90",
    "volume_ma7", "fear_greed_norm",
    "dxy_trend", "equity_regime", "vix_high", "rate_pressure",
]

XGB_PARAMS = {
    "n_estimators":     500,
    "max_depth":        6,
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
    "gamma":            0.1,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "eval_metric":      "logloss",
    "random_state":     42,
    "n_jobs":           -1
}

TRAIN_RATIO = 0.8


def load_data(symbol: str = SYMBOL) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{symbol}_1d.csv")
    df   = pd.read_csv(path, index_col="timestamp", parse_dates=True)
    df   = df[df.index >= "2020-01-01"]
    available = [f for f in FEATURES if f in df.columns]
    missing   = [f for f in FEATURES if f not in df.columns]
    if missing:
        log.warning(f"Features manquantes : {missing}")
    df = df[available + ["target_direction"]].dropna()
    log.info(f"Donnees : {df.shape[0]} lignes ({df.index[0].date()} -> {df.index[-1].date()})")
    return df


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:

    for col in ["close", "returns", "rsi", "volume"]:
        if col in df.columns:
            for lag in [1, 2, 3]:
                df[f"{col}_lag{lag}"] = df[col].shift(lag)
    df["momentum_5"]  = df["close"] / df["close"].shift(5) - 1
    df["momentum_10"] = df["close"] / df["close"].shift(10) - 1
    df["momentum_20"] = df["close"] / df["close"].shift(20) - 1
    df["rsi_overbought"] = (df["rsi"] > 70).astype(int)
    df["rsi_oversold"]   = (df["rsi"] < 30).astype(int)
    df["macd_cross"] = (df["macd"] > df["macd_signal"]).astype(int)
    if "bb_upper" in df.columns:
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-10)
    df["trend_2w"] = (df["close"] > df["close"].shift(14)).astype(int)
    df["trend_1m"] = (df["close"] > df["close"].shift(30)).astype(int)
    df["volume_spike"] = (df["volume"] > df["volume_ma7"] * 1.5).astype(int)
    direction = df["returns"].apply(lambda x: 1 if x > 0 else -1)
    df["streak"] = direction.groupby(
        (direction != direction.shift()).cumsum()
    ).cumcount() + 1
    for col in ["dxy_trend", "equity_regime", "vix_high", "rate_pressure"]:
        if col in df.columns:
            df[f"{col}_lag1"] = df[col].shift(1)
            df[f"{col}_lag3"] = df[col].shift(3)

    df.dropna(inplace=True)
    return df


def walk_forward_validation(df, n_splits=5):
    """Évalue le modèle sur plusieurs périodes successives."""
    from sklearn.model_selection import TimeSeriesSplit
    tscv    = TimeSeriesSplit(n_splits=n_splits, gap=7)
    scores  = []
    for train_idx, test_idx in tscv.split(df):
        X_train = df.iloc[train_idx][[c for c in df.columns if c != 'target_direction']]
        y_train = df.iloc[train_idx]['target_direction']
        X_test  = df.iloc[test_idx][[c for c in df.columns if c != 'target_direction']]
        y_test  = df.iloc[test_idx]['target_direction']
        model   = XGBClassifier(**XGB_PARAMS)
        model.fit(X_train, y_train)
        scores.append(accuracy_score(y_test, model.predict(X_test)))
    return np.mean(scores), np.std(scores)


def train_model(X_train, y_train):
    model = XGBClassifier(**XGB_PARAMS)
    tscv  = TimeSeriesSplit(n_splits=5)
    splits = list(tscv.split(X_train))
    last_train_idx, last_val_idx = splits[-1]
    X_tr  = X_train.iloc[last_train_idx]
    X_val = X_train.iloc[last_val_idx]
    y_tr  = y_train.iloc[last_train_idx]
    y_val = y_train.iloc[last_val_idx]
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=50)
    return model


def evaluate(model, X_test, y_test):
    preds  = model.predict(X_test)
    probas = model.predict_proba(X_test)[:, 1]
    acc    = accuracy_score(y_test, preds)
    f1     = f1_score(y_test, preds, average="weighted")
    auc    = roc_auc_score(y_test, probas)
    log.info(f"Accuracy : {acc:.4f} ({acc*100:.1f}%)")
    log.info(f"F1 Score : {f1:.4f}")
    log.info(f"AUC-ROC  : {auc:.4f}")
    log.info("\n" + classification_report(y_test, preds, target_names=["Baisse", "Hausse"]))
    return preds, probas, {"accuracy": acc, "f1": f1, "auc_roc": auc}


def predict_next_day(model, df: pd.DataFrame) -> dict:
    import numpy as np
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    features     = [c for c in numeric_cols if c != "target_direction"]
    last_row     = df[features].iloc[[-1]]
    direction    = int(model.predict(last_row)[0])
    proba        = float(model.predict_proba(last_row)[0][direction])
    return {
        "direction":   direction,
        "probability": round(proba, 4),
        "signal":      "HAUSSE" if direction == 1 else "BAISSE",
        "confidence":  "Forte" if proba > 0.65 else "Moyenne" if proba > 0.55 else "Faible",
        "tradeable":   proba > 0.65,
    }


def save_model(model, feature_names, symbol=SYMBOL):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model,         f"{MODEL_DIR}/{symbol}_xgboost.pkl")
    joblib.dump(feature_names, f"{MODEL_DIR}/{symbol}_xgb_features.pkl")
    log.info(f"Modele XGBoost sauvegarde dans {MODEL_DIR}/")


def load_xgb_model(symbol=SYMBOL):
    model    = joblib.load(f"{MODEL_DIR}/{symbol}_xgboost.pkl")
    features = joblib.load(f"{MODEL_DIR}/{symbol}_xgb_features.pkl")
    return model, features


def time_split(df: pd.DataFrame):
    features = [c for c in df.columns if c != "target_direction"]
    X        = df[features]
    y        = df["target_direction"]
    split    = int(len(df) * TRAIN_RATIO)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]
    log.info(f"Train : {len(X_train)} | Test : {len(X_test)}")
    return X_train, X_test, y_train, y_test, features


def run(symbol=SYMBOL):
    log.info(f"=== XGBoost Pipeline : {symbol} ===")
    df = load_data(symbol)
    df = add_lag_features(df)

    X_train, X_test, y_train, y_test, feature_names = time_split(df)

    model         = train_model(X_train, y_train)
    _, _, metrics = evaluate(model, X_test, y_test)
    prediction    = predict_next_day(model, df)
    save_model(model, feature_names, symbol)
    log.info(f"Signal : {prediction['signal']} ({prediction['probability']*100:.1f}%)")
    return model, metrics, prediction


if __name__ == "__main__":
    SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
    for sym in SYMBOLS:
        try:
            model, metrics, pred = run(sym)
            print(f"\n{sym}")
            print(f"  Accuracy : {metrics['accuracy']*100:.1f}%")
            print(f"  Signal   : {pred['signal']} ({pred['probability']*100:.1f}%)")
        except Exception as e:
            log.error(f"Erreur {sym} : {e}")