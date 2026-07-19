"""
Crypto Predict — Pipeline d'entrainement (sans MLflow)
"""
import os, sys, logging, time
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib
import matplotlib
matplotlib.use("Agg")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(__file__))

from lstm_model import (
    CryptoLSTM, CryptoDataset,
    load_data, split_and_scale, predict_future,
    DEVICE, BATCH_SIZE, MODEL_DIR,
    train_model, evaluate,
)


def train_lstm(symbol: str):
    """Entraine et sauvegarde le modele LSTM localement."""
    import math

    df = load_data(symbol)
    train_scaled, test_scaled, scaler, target_scaler, target_idx, _ = split_and_scale(df)

    train_ds = CryptoDataset(train_scaled, target_idx)
    test_ds  = CryptoDataset(test_scaled,  target_idx)
    val_size = int(len(train_ds) * 0.1)
    train_ds, val_ds = torch.utils.data.random_split(
        train_ds, [len(train_ds) - val_size, val_size]
    )

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE)
    test_loader  = DataLoader(test_ds,  batch_size=BATCH_SIZE)

    model = CryptoLSTM(input_size=train_scaled.shape[1]).to(DEVICE)
    log.info(f"Parametres LSTM : {sum(p.numel() for p in model.parameters()):,}")

    model, history = train_model(model, train_loader, val_loader)
    _, _, metrics  = evaluate(model, test_loader, target_scaler)

    all_scaled    = np.concatenate([train_scaled, test_scaled])
    future_prices = predict_future(model, all_scaled, target_scaler)

    log.info(f"[LSTM] RMSE={metrics['rmse']:,.2f} | MAE={metrics['mae']:,.2f} | MAPE={metrics['mape']:.2f}%")
    log.info(f"[LSTM] Prediction {len(future_prices)}j : {[f'${p:,.0f}' for p in future_prices]}")

    # Sauvegarder localement
    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(model.state_dict(), f"{MODEL_DIR}/{symbol}_lstm.pt")
    joblib.dump(scaler,            f"{MODEL_DIR}/{symbol}_scaler.pkl")
    joblib.dump(target_scaler,     f"{MODEL_DIR}/{symbol}_target_scaler.pkl")
    log.info(f"Modele sauvegarde dans {MODEL_DIR}/")

    run_id = f"local_{int(time.time())}"
    return run_id, metrics, future_prices.tolist()


def train_with_mlflow(symbol: str):
    """Lance LSTM + XGBoost pour un symbole."""
    log.info(f"\n{'='*50}")
    log.info(f"LSTM — {symbol}")
    log.info('='*50)
    run_id, lstm_metrics, future = train_lstm(symbol)

    log.info(f"\n{'='*50}")
    log.info(f"XGBoost — {symbol}")
    log.info('='*50)
    xgb_metrics = {}
    prediction  = {}
    try:
        from xgboost_model import run as run_xgb
        _, xgb_metrics, prediction = run_xgb(symbol)
        log.info(f"XGBoost Accuracy : {xgb_metrics['accuracy']*100:.1f}%")
        log.info(f"Signal demain    : {prediction['signal']} ({prediction['probability']*100:.1f}%)")
    except Exception as e:
        log.error(f"XGBoost echoue : {e}")

    return run_id, lstm_metrics, future


if __name__ == "__main__":
    SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
    for sym in SYMBOLS:
        try:
            run_id, metrics, future = train_with_mlflow(sym)
            print(f"\n{'='*40}")
            print(f"{sym} — LSTM")
            print(f"  RMSE   : ${metrics['rmse']:,.2f}")
            print(f"  MAPE   : {metrics['mape']:.2f}%")
            print(f"  run_id : {run_id}")
        except Exception as e:
            log.error(f"Erreur {sym} : {e}")