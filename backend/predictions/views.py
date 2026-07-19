import os, logging
import numpy as np
import pandas as pd
import torch
import joblib
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAdminUser
from django.core.cache import cache

log = logging.getLogger(__name__)

FORECAST_DAYS = 7
WINDOW_SIZE   = 60


# ══════════════════════════════════════════════
# MODEL LOADER
# ══════════════════════════════════════════════

class ModelLoader:
    _cache = {}

    @classmethod
    def get(cls, symbol):
        if symbol not in cls._cache:
            cls._cache[symbol] = cls._load(symbol)
        return cls._cache[symbol]

    @classmethod
    def _load(cls, symbol):
        import sys
        sys.path.insert(0, "/app/ml")

        # Importer FEATURES depuis lstm_model (source unique de vérité)
        from lstm_model import CryptoLSTM, FEATURES, MODEL_DIR

        model_path  = f"{MODEL_DIR}/{symbol}_lstm.pt"
        scaler_path = f"{MODEL_DIR}/{symbol}_scaler.pkl"
        target_path = f"{MODEL_DIR}/{symbol}_target_scaler.pkl"

        if not os.path.exists(model_path):
            raise ValueError(
                f"Modele non trouve pour {symbol}. Lancez un entrainement."
            )

        csv_path  = f"/app/ml/data/{symbol}_1d.csv"
        df        = pd.read_csv(csv_path, index_col="timestamp", parse_dates=True)

        # Garder uniquement les features disponibles dans le CSV
        available = [f for f in FEATURES if f in df.columns]

        model = CryptoLSTM(input_size=len(available))
        model.load_state_dict(torch.load(model_path, map_location="cpu"))
        model.eval()

        scaler        = joblib.load(scaler_path)
        target_scaler = joblib.load(target_path)

        # Metriques depuis la DB
        metrics = {
            "rmse": None, "mae": None, "mape": None,
            "version": "local", "run_id": "local",
        }
        try:
            from predictions.models import ModelMetric
            m = ModelMetric.objects.filter(
                symbol=symbol, model_type="lstm"
            ).order_by("-created_at").first()
            if m:
                metrics = {
                    "rmse":    m.rmse,
                    "mae":     m.mae,
                    "mape":    m.mape,
                    "version": str(m.model_version),
                    "run_id":  m.run_id,
                }
        except Exception:
            pass

        return {
            "model":         model,
            "scaler":        scaler,
            "target_scaler": target_scaler,
            "available":     available, 
            "metrics":       metrics,
        }

    @classmethod
    def reload(cls, symbol):
        cls._cache.pop(symbol, None)


# ══════════════════════════════════════════════
# SERIALIZERS
# ══════════════════════════════════════════════

class TrainingJobSerializer(serializers.ModelSerializer):
    class Meta:
        from predictions.models import TrainingJob
        model  = TrainingJob
        fields = (
            "id", "symbol", "status", "progress", "current_step",
            "log", "lstm_rmse", "lstm_mape", "xgb_accuracy",
            "run_id", "started_at", "finished_at",
        )


# ══════════════════════════════════════════════
# PREDICTION
# ══════════════════════════════════════════════

class PredictView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, symbol):
        symbol    = symbol.upper()
        cache_key = f"pred_{symbol}"
        if cached := cache.get(cache_key):
            return Response(cached)
        try:
            loader        = ModelLoader.get(symbol)
            model         = loader["model"]
            target_scaler = loader["target_scaler"]
            available     = loader["available"]

            csv_path = f"/app/ml/data/{symbol}_1d.csv"
            df       = pd.read_csv(csv_path, index_col="timestamp", parse_dates=True)
            price_cols = ["close", "bb_upper", "bb_middle", "bb_lower",
                        "price_ma7", "price_ma30", "price_ma90"]
            for col in price_cols:
                if col in df.columns:
                    df[col] = np.log1p(df[col])
            scaled   = loader["scaler"].transform(
                df[available].dropna().tail(WINDOW_SIZE).values
            )
            x = torch.tensor(scaled, dtype=torch.float32).unsqueeze(0)

            with torch.no_grad():
                pred_norm = model(x).numpy().flatten()

            prices     = target_scaler.inverse_transform(pred_norm.reshape(-1, 1)).flatten()
            last_real_price = float(np.expm1(df["close"].iloc[-1]))
            drift = prices[0] - last_real_price
            prices = prices - drift

            prices = np.nan_to_num(prices, nan=last_real_price, posinf=last_real_price, neginf=last_real_price)
            log.info(f"[{symbol}] prices après correction: {prices}")

            last_price = last_real_price
            last_date  = df.index[-1]
            lstm_direction = 1 if float(prices[0]) > last_price else 0

            # ── Signal XGBoost
            xgb_signal = None
            try:
                import sys; sys.path.insert(0, "/app/ml")
                from xgboost_model import load_xgb_model, add_lag_features
                
                xgb_model, xgb_features = load_xgb_model(symbol)
                df_raw = pd.read_csv(csv_path, index_col="timestamp", parse_dates=True) 
                df_xgb    = add_lag_features(df_raw.copy())
                numeric_cols = df_xgb.select_dtypes(include=[np.number]).columns.tolist()
                xgb_features     = [c for c in numeric_cols if c != "target_direction"]
                last_row  = df_xgb[xgb_features].iloc[[-1]] 
                xgb_dir   = int(xgb_model.predict(last_row)[0])
                xgb_proba = float(xgb_model.predict_proba(last_row)[0][xgb_dir])
                xgb_signal = {
                    "direction":   xgb_dir,
                    "probability": round(xgb_proba, 4),
                    "signal":      "HAUSSE" if xgb_dir == 1 else "BAISSE",
                    "confidence":  "Forte" if xgb_proba > 0.65 else
                                   "Moyenne" if xgb_proba > 0.55 else "Faible",
                    "tradeable":   xgb_proba > 0.60,
                }
            except Exception as e:
                log.warning(f"XGBoost signal indisponible : {e}")
                import traceback
                log.warning(traceback.format_exc()) 

            # ── Signal ensemble (LSTM + XGBoost)
            ensemble = None
            if xgb_signal:
                agree = lstm_direction == xgb_signal["direction"]
                ensemble = {
                    "signal":    "HAUSSE" if lstm_direction == 1 else "BAISSE",
                    "agreement": agree,
                    "strength":  "FORT"          if agree and xgb_signal["tradeable"] else
                                 "MOYEN"         if agree else
                                 "CONTRADICTOIRE",
                    "tradeable": agree and xgb_signal["tradeable"],
                }
            news_sentiment = 0.0
            try:
                from news_collector import get_current_sentiment
                news_sentiment = get_current_sentiment(symbol)
            except Exception:
                pass

            result = {
                "symbol":    symbol,
                "generated": datetime.utcnow().isoformat(),
                "forecast":  [
                    {"date":  (last_date + timedelta(days=i+1)).strftime("%Y-%m-%d"),
                     "price": round(float(p), 2)}
                    for i, p in enumerate(prices)
                ],
                "model_info":  loader["metrics"],
                "xgb_signal":  xgb_signal, 
                "ensemble":    ensemble,
                "news_sentiment": news_sentiment
            }
            cache.set(cache_key, result, timeout=3600)
            return Response(result)

        except ValueError as e:
            return Response({"error": str(e)}, status=503)
        except Exception as e:
            log.error(f"Prediction error {symbol}: {e}")
            return Response({"error": str(e)}, status=500)

class ModelMetricsView(APIView):
    
    permission_classes = [AllowAny]

    def get(self, request, symbol):
        try:
            return Response(ModelLoader.get(symbol.upper())["metrics"])
        except Exception as e:
            return Response({"error": str(e)}, status=404)


class PricesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, symbol):
        try:
            csv_path = f"/app/ml/data/{symbol.upper()}_1d.csv"
            df       = pd.read_csv(csv_path, index_col="timestamp", parse_dates=True)

            period = request.query_params.get("period", "3m")
            PERIODS = {
                "1w":  7,
                "1m":  30,
                "3m":  90,
                "6m":  180,
                "1y":  365,
                "2y":  730,
                "all": len(df),
            }
            days = PERIODS.get(period, 90)
            df   = df.tail(days)

            data = [
                {"date": str(idx.date()), "price": row["close"]}
                for idx, row in df.iterrows()
            ]
            return Response({"symbol": symbol, "prices": data, "period": period})
        except Exception as e:
            return Response({"error": str(e)}, status=404)


class LivePriceView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, symbol):
        YAHOO = {
            "BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD",
            "BNBUSDT": "BNB-USD", "SOLUSDT": "SOL-USD", "XRPUSDT": "XRP-USD",
        }
        try:
            import yfinance as yf
            ticker = YAHOO.get(symbol.upper())
            if not ticker:
                return Response({"error": "Symbole inconnu"}, status=404)
            hist  = yf.Ticker(ticker).history(period="1d", interval="1m")
            if hist.empty:
                return Response({"error": "Prix indisponible"}, status=503)
            price = round(float(hist["Close"].iloc[-1]), 2)
            prev  = round(float(hist["Close"].iloc[0]), 2)
            return Response({
                "symbol": symbol.upper(),
                "price":  price,
                "change": round(((price - prev) / prev) * 100, 2),
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        
# ══════════════════════════════════════════════
# ENTRAINEMENT
# ══════════════════════════════════════════════

class TrainView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        from predictions.models import TrainingJob
        from predictions.tasks import train_model_task

        symbol = request.data.get("symbol", "BTCUSDT").upper()
        job    = TrainingJob.objects.create(symbol=symbol, status="PENDING")
        task   = train_model_task.delay(symbol, job.id)
        job.task_id = task.id
        job.save(update_fields=["task_id"])
        return Response({"job": TrainingJobSerializer(job).data}, status=202)


class TrainingJobDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, job_id):
        from predictions.models import TrainingJob
        try:
            job = TrainingJob.objects.get(id=job_id)
        except TrainingJob.DoesNotExist:
            return Response({"error": "Job introuvable"}, status=404)
        return Response(TrainingJobSerializer(job).data)


class TrainingHistoryView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class   = TrainingJobSerializer

    def get_queryset(self):
        from predictions.models import TrainingJob
        return TrainingJob.objects.all()[:20]


class TrainStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, task_id):
        from celery.result import AsyncResult
        r = AsyncResult(task_id)
        return Response({
            "task_id": task_id,
            "status":  r.status,
            "result":  r.result if r.ready() else None,
        })
    
class AdminDataView(APIView):
    """Vue d'ensemble des données disponibles pour l'entraînement."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        from predictions.models import OHLCVData, MacroData, FearGreedData, FuturesData

        SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT"]
        overview = []

        for symbol in SYMBOLS:
            rows = OHLCVData.objects.filter(symbol=symbol)
            if rows.exists():
                first = rows.order_by("timestamp").first()
                last  = rows.order_by("-timestamp").first()
                overview.append({
                    "symbol":     symbol,
                    "rows":       rows.count(),
                    "date_start": str(first.timestamp),
                    "date_end":   str(last.timestamp),
                    "has_csv":    os.path.exists(f"/app/ml/data/{symbol}_1d.csv"),
                })
            else:
                overview.append({
                    "symbol": symbol, "rows": 0,
                    "date_start": None, "date_end": None,
                    "has_csv": os.path.exists(f"/app/ml/data/{symbol}_1d.csv"),
                })

        macro_count = MacroData.objects.count()
        fg_count    = FearGreedData.objects.count()

        return Response({
            "symbols":     overview,
            "macro_rows":  macro_count,
            "fg_rows":     fg_count,
            "models": {
                s: {
                    "lstm":    os.path.exists(f"/app/ml/models/{s}_lstm.pt"),
                    "xgboost": os.path.exists(f"/app/ml/models/{s}_xgboost.pkl"),
                }
                for s in SYMBOLS
            }
        })


class AdminSymbolDataView(APIView):
    """Dernières lignes OHLCV pour un symbole."""
    permission_classes = [IsAdminUser]

    def get(self, request, symbol):
        from predictions.models import OHLCVData, ModelMetric
        rows = OHLCVData.objects.filter(
            symbol=symbol.upper()
        ).order_by("-timestamp")[:100]

        data = [{
            "date":       str(r.timestamp),
            "open":       r.open,   "high": r.high,
            "low":        r.low,    "close": r.close,
            "volume":     r.volume,
            "rsi":        r.rsi,    "macd": r.macd,
            "returns":    r.returns,
            "volatility": r.volatility,
            "fear_greed": None,
        } for r in rows]

        metrics = ModelMetric.objects.filter(
            symbol=symbol.upper()
        ).order_by("-created_at")[:5]

        return Response({
            "symbol":  symbol.upper(),
            "data":    data,
            "metrics": [{
                "model_type":    m.model_type,
                "rmse":          m.rmse,
                "mape":          m.mape,
                "accuracy":      m.accuracy,
                "model_version": m.model_version,
                "created_at":    str(m.created_at),
            } for m in metrics]
        })