"""
Crypto Predict — LSTM Model
"""
import os, math, logging
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── CONFIG
SYMBOL      = "BTCUSDT"
DATA_DIR    = os.path.join(os.path.dirname(__file__), "data")
MODEL_DIR   = os.path.join(os.path.dirname(__file__), "models")

WINDOW_SIZE   = 30
FORECAST_DAYS = 7

FEATURES = [
    "close", "volume",
    "rsi",
    "macd", "macd_signal", "macd_diff",
    "bb_upper", "bb_middle", "bb_lower", "bb_width",
    "returns", "log_returns", "volatility",
    "price_ma7", "price_ma30", "price_ma90",
    "volume_ma7",
    "fear_greed_norm",
    "dxy_trend",
    "equity_regime",
    "vix_high", 
    "rate_pressure"
]
TARGET = "close"

HIDDEN_SIZE   = 64
NUM_LAYERS    = 2
DROPOUT       = 0.2
BATCH_SIZE    = 32
EPOCHS        = 150
LEARNING_RATE = 1e-3
TRAIN_RATIO   = 0.8

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ── 1. CHARGEMENT
def load_data(symbol: str = SYMBOL) -> pd.DataFrame:
    path      = os.path.join(DATA_DIR, f"{symbol}_1d.csv")
    df        = pd.read_csv(path, index_col="timestamp", parse_dates=True)
    df        = df[df.index >= "2020-01-01"]

    available = [f for f in FEATURES if f in df.columns]
    missing   = [f for f in FEATURES if f not in df.columns]
    if missing:
        log.warning(f"Features manquantes (ignorees) : {missing}")
    df = df[available].dropna()

    return df


def split_and_scale(df):

    PRICE_COLS = ["close", "bb_upper", "bb_middle", "bb_lower",
                "price_ma7", "price_ma30", "price_ma90"]

    df = df.copy()
    for col in PRICE_COLS:
        if col in df.columns:
            df[col] = np.log1p(df[col])

    log.info(f"close après log1p: min={df['close'].min():.2f} max={df['close'].max():.2f}")

    split        = int(len(df) * TRAIN_RATIO)
    train_df     = df.iloc[:split]
    test_df      = df.iloc[split:]
    scaler       = MinMaxScaler(feature_range=(0, 1))
    train_scaled = scaler.fit_transform(train_df.values)
    test_scaled  = scaler.transform(test_df.values)
    target_idx    = list(df.columns).index(TARGET)
    target_scaler = MinMaxScaler(feature_range=(0, 1))
    target_scaler.fit(train_df[[TARGET]].values)
    log.info(f"target_scaler: min={target_scaler.data_min_[0]:.2f} max={target_scaler.data_max_[0]:.2f}")
    log.info(f"Train : {len(train_df)} | Test : {len(test_df)}")
    return train_scaled, test_scaled, scaler, target_scaler, target_idx, df.index[split:]

# ── 2. DATASET
class CryptoDataset(Dataset):
    def __init__(self, data, target_idx, window=WINDOW_SIZE, forecast=FORECAST_DAYS):
        self.data       = data
        self.target_idx = target_idx
        self.window     = window
        self.forecast   = forecast

    def __len__(self):
        return len(self.data) - self.window - self.forecast + 1

    def __getitem__(self, idx):
        x = self.data[idx : idx + self.window]
        y = self.data[idx + self.window : idx + self.window + self.forecast, self.target_idx]
        return torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


# ── 3. MODELE
class CryptoLSTM(nn.Module):
    def __init__(self, input_size, hidden_size=HIDDEN_SIZE, num_layers=NUM_LAYERS,
                 dropout=DROPOUT, forecast_days=FORECAST_DAYS):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers,
            dropout=dropout if num_layers > 1 else 0,
            batch_first=True,
        )
        self.attention = nn.MultiheadAttention(hidden_size, num_heads=4, batch_first=True)  # ← ajouté
        self.norm = nn.LayerNorm(hidden_size)
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, forecast_days),
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)
        out = self.norm(attn_out[:, -1])
        return self.head(out)


# ── 4. ENTRAINEMENT
def train_model(model, train_loader, val_loader, patience=10):
    optimizer  = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler  = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion  = nn.MSELoss()
    best_val   = float("inf")
    best_state = None
    stagnation = 0
    history    = {"train": [], "val": []}

    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss = (
            sum(_step(model, x, y, optimizer, criterion) for x, y in train_loader)
            / len(train_loader)
        )
        model.eval()
        with torch.no_grad():
            val_losses = [criterion(model(x.to(DEVICE)), y.to(DEVICE)).item() for x, y in val_loader]
            val_loss   = sum(val_losses) / max(len(val_losses), 1)

        # Ignorer les NaN
        if not np.isnan(val_loss) and val_loss < best_val:
            best_val   = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            stagnation = 0
        else:
            stagnation += 1
            if stagnation >= patience:
                log.info(f"Early stopping à l'epoch {epoch}")
                break

        scheduler.step(val_loss)
        history["train"].append(train_loss)
        history["val"].append(val_loss)

        if epoch % 5 == 0 or epoch == 1:
            log.info(f"Epoch {epoch:3d}/{EPOCHS} | train={train_loss:.6f} | val={val_loss:.6f}")

    if best_state is not None:
        model.load_state_dict(best_state)
        log.info(f"Meilleur val loss : {best_val:.6f}")
    else:
        log.warning("best_state est None — conservation du dernier état")

    return model, history

def _step(model, x, y, optimizer, criterion):
    x, y = x.to(DEVICE), y.to(DEVICE)
    optimizer.zero_grad()
    loss = criterion(model(x), y)
    loss.backward()
    nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    optimizer.step()
    return loss.item()


# ── 5. EVALUATION
def evaluate(model, test_loader, target_scaler):
    model.eval()
    all_preds, all_targets = [], []
    with torch.no_grad():
        for x, y in test_loader:
            all_preds.append(model(x.to(DEVICE)).cpu().numpy())
            all_targets.append(y.numpy())

    preds   = np.concatenate(all_preds)
    targets = np.concatenate(all_targets)

    # Vérifier NaN avant inverse_transform
    if np.isnan(preds).any():
        log.warning(f"NaN dans les prédictions — {np.isnan(preds).sum()} valeurs")
        preds = np.nan_to_num(preds, nan=0.5)

    p_log  = target_scaler.inverse_transform(preds.reshape(-1,1)).flatten()
    t_log  = target_scaler.inverse_transform(targets.reshape(-1,1)).flatten()
    p_real = np.expm1(p_log)
    t_real = np.expm1(t_log)

    # mask   = (t_real > 1e-6) & (p_real > 0) & np.isfinite(p_real) & np.isfinite(t_real)
    # t_real = t_real[mask]
    # p_real = p_real[mask]

    rmse = math.sqrt(mean_squared_error(t_real, p_real))
    mae  = mean_absolute_error(t_real, p_real)
    mape = float(np.mean(np.abs((t_real - p_real) / t_real)) * 100)

    log.info(f"RMSE={rmse:,.2f} | MAE={mae:,.2f} | MAPE={mape:.2f}%")
    return p_real, t_real, {"rmse": rmse, "mae": mae, "mape": mape}


# ── 6. PREDICTION FUTURE
def predict_future(model, data_scaled, target_scaler, n_days=FORECAST_DAYS):
    model.eval()
    x = torch.tensor(
        data_scaled[-WINDOW_SIZE:], dtype=torch.float32
    ).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        pred = model(x).cpu().numpy().flatten()
    log_prices = target_scaler.inverse_transform(pred.reshape(-1, 1)).flatten()
    return np.expm1(log_prices)

# ── 7. SAUVEGARDE / CHARGEMENT
def save_model(model, scaler, target_scaler, symbol=SYMBOL):
    os.makedirs(MODEL_DIR, exist_ok=True)
    torch.save(model.state_dict(), f"{MODEL_DIR}/{symbol}_lstm.pt")
    joblib.dump(scaler,            f"{MODEL_DIR}/{symbol}_scaler.pkl")
    joblib.dump(target_scaler,     f"{MODEL_DIR}/{symbol}_target_scaler.pkl")
    log.info(f"Modele sauvegarde dans {MODEL_DIR}/")


def load_model(symbol, input_size):
    model = CryptoLSTM(input_size=input_size).to(DEVICE)
    model.load_state_dict(
        torch.load(f"{MODEL_DIR}/{symbol}_lstm.pt", map_location=DEVICE)
    )
    scaler        = joblib.load(f"{MODEL_DIR}/{symbol}_scaler.pkl")
    target_scaler = joblib.load(f"{MODEL_DIR}/{symbol}_target_scaler.pkl")
    model.eval()
    return model, scaler, target_scaler


# ── 8. PIPELINE COMPLET
def run(symbol=SYMBOL):
    log.info(f"=== LSTM Pipeline : {symbol} | Device : {DEVICE} ===")
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
    log.info(f"Parametres : {sum(p.numel() for p in model.parameters()):,}")

    model, history      = train_model(model, train_loader, val_loader)
    preds, targets, metrics = evaluate(model, test_loader, target_scaler)

    all_scaled    = np.concatenate([train_scaled, test_scaled])
    future_prices = predict_future(model, all_scaled, target_scaler)
    log.info(f"Prediction {FORECAST_DAYS}j : {[f'${p:,.0f}' for p in future_prices]}")

    save_model(model, scaler, target_scaler, symbol)
    return model, metrics, future_prices


if __name__ == "__main__":
    model, metrics, future = run(SYMBOL)
    print(f"\nRMSE : ${metrics['rmse']:,.2f}")
    print(f"MAE  : ${metrics['mae']:,.2f}")
    print(f"MAPE : {metrics['mape']:.2f}%")
    for i, p in enumerate(future, 1):
        print(f"  J+{i} : ${p:,.2f}")